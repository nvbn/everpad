from BeautifulSoup import BeautifulSoup
from sqlalchemy.orm.exc import NoResultFound
from everpad.tools import sanitize
from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.limits import constants as limits
from evernote.edam.type import ttypes
from evernote.edam.notestore.ttypes import NoteFilter
from ... import const
from .. import models
from .base import BaseSync
import time
import binascii


class ShareNoteMixin(object):
    """Mixin with methods for sharing notes"""

    def _get_shard_id(self):
        """Receive shard id, not cached because can change"""
        return self.user_store.getUser(self.auth_token).shardId

    def _share_note(self, note, share_date=None):
        """Share or receive info about sharing"""
        try:
            share_key = self.note_store.shareNote(self.auth_token, note.guid)
            note.share_url = "https://www.evernote.com/shard/{}/sh/{}/{}".format(
                self._get_shard_id(), note.guid, share_key,
            )
            note.share_date = share_date or int(time.time() * 1000)
            note.share_status = const.SHARE_SHARED
            self.session.commit()
        except EDAMUserException as e:
            note.share_status = const.SHARE_NONE
            self.app.log('Sharing note %s failed' % note.title)
            self.app.log(e)

    def _stop_sharing_note(self, note):
        """Stop sharing note"""
        note.share_status = const.SHARE_NONE
        note.share_date = None
        note.share_url = None
        self.session.commit()


class PushNote(BaseSync, ShareNoteMixin):
    """Push note to remote server"""

    def push(self):
        """Push note to remote server"""
        for note in self.session.query(models.Note).filter(
            ~models.Note.action.in_((
                const.ACTION_NONE, const.ACTION_NOEXSIST, const.ACTION_CONFLICT,
            ))
        ):
            self.app.log('Pushing note "%s" to remote server.' % note.title)
            note_ttype = self._create_ttype(note)

            if note.action == const.ACTION_CREATE:
                self._push_new_note(note, note_ttype)
            elif note.action == const.ACTION_CHANGE:
                self._push_changed_note(note, note_ttype)
            elif note.action == const.ACTION_DELETE:
                self._delete_note(note, note_ttype)

            if note.share_status == const.SHARE_NEED_SHARE:
                self._share_note(note)
            elif note.share_status == const.SHARE_NEED_STOP:
                self._stop_sharing_note(note)

        self.session.commit()

    def _create_ttype(self, note):
        """Create ttype for note"""
        kwargs = dict(
            title=note.title[:limits.EDAM_NOTE_TITLE_LEN_MAX].strip().encode('utf8'),
            content=self._prepare_content(note.content),
            tagGuids=map(
                lambda tag: tag.guid, note.tags,
            ),
            resources=self._prepare_resources(note),
        )

        if note.notebook:
            kwargs['notebookGuid'] = note.notebook.guid

        if note.guid:
            kwargs['guid'] = note.guid

        return ttypes.Note(**kwargs)

    def _prepare_resources(self, note):
        """Prepare note resources"""
        return map(
            lambda resource: ttypes.Resource(
                noteGuid=note.guid,
                data=ttypes.Data(body=open(resource.file_path).read()),
                mime=resource.mime,
                attributes=ttypes.ResourceAttributes(
                    fileName=resource.file_name.encode('utf8'),
                ),
            ), self.session.query(models.Resource).filter(
                (models.Resource.note_id == note.id)
                & (models.Resource.action != const.ACTION_DELETE)
            ),
        )

    def _prepare_content(self, content):
        """Prepare content"""
        enml_content = (u"""
            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
            <en-note>{}</en-note>
        """.format(sanitize(
            html=content[:limits.EDAM_NOTE_CONTENT_LEN_MAX]
        ))).strip().encode('utf8')

        soup = BeautifulSoup(enml_content, selfClosingTags=[
            'img', 'en-todo', 'en-media', 'br', 'hr',
        ])

        return str(soup)

    def _push_new_note(self, note, note_ttype):
        """Push new note to remote"""
        try:
            note_ttype = self.note_store.createNote(self.auth_token, note_ttype)
            note.guid = note_ttype.guid
        except EDAMUserException as e:
            note.action = const.ACTION_NONE
            self.app.log('Push new note "%s" failed.' % note.title)
            self.app.log(e)
        finally:
            note.action = const.ACTION_NONE

    def _push_changed_note(self, note, note_ttype):
        """Push changed note to remote"""
        try:
            self.note_store.updateNote(self.auth_token, note_ttype)
        except EDAMUserException as e:
            self.app.log('Push changed note "%s" failed.' % note.title)
            self.app.log(note_ttype)
            self.app.log(note)
            self.app.log(e)
        finally:
            note.action = const.ACTION_NONE

    def _delete_note(self, note, note_ttype):
        """Delete note"""
        try:
            self.note_store.deleteNote(self.auth_token, note_ttype.guid)
        except EDAMUserException as e:
            self.app.log('Note %s already removed' % note.title)
            self.app.log(e)
        finally:
            self.session.delete(note)


class PullNote(BaseSync, ShareNoteMixin):
    """Pull notes"""

    def __init__(self, *args, **kwargs):
        super(PullNote, self).__init__(*args, **kwargs)
        self._exists = []

    def pull(self):
        """Pull notes from remote server"""
        for note_ttype in self._get_all_notes():
            self.app.log(
                'Pulling note "%s" from remote server.' % note_ttype.title)
            try:
                note = self._update_note(note_ttype)
            except NoResultFound:
                note = self._create_note(note_ttype)
            self._exists.append(note.id)

            self._check_sharing_information(note, note_ttype)

            resource_ids = self._receive_resources(note, note_ttype)
            if resource_ids:
                self._remove_resources(note, resource_ids)

        self.session.commit()
        self._remove_notes()

    def _get_all_notes(self):
        """Iterate all notes"""
        offset = 0

        while True:
            note_list = self.note_store.findNotes(
                self.auth_token, NoteFilter(
                    order=ttypes.NoteSortOrder.UPDATED,
                    ascending=False,
                ), offset, limits.EDAM_USER_NOTES_MAX,
            )

            for note in note_list.notes:
                yield note

            offset = note_list.startIndex + len(note_list.notes)
            if note_list.totalNotes - offset <= 0:
                break

    def _get_full_note(self, note_ttype):
        """Get full note"""
        return self.note_store.getNote(
            self.auth_token, note_ttype.guid,
            True, True, True, True,
        )

    def _create_note(self, note_ttype):
        """Create new note"""
        note_ttype = self._get_full_note(note_ttype)

        note = models.Note(guid=note_ttype.guid)
        note.from_api(note_ttype, self.session)
        self.session.add(note)
        self.session.commit()
        return note

    def _update_note(self, note_ttype):
        """Update changed note"""
        note = self.session.query(models.Note).filter(
            models.Note.guid == note_ttype.guid,
        ).one()

        note_ttype = self._get_full_note(note_ttype)

        if note.updated < note_ttype.updated:
            if note.action == const.ACTION_CHANGE:
                self._create_conflict(note, note_ttype)
            else:
                note.from_api(note_ttype, self.session)
        return note

    def _create_conflict(self, note, note_ttype):
        """Create conflict note"""
        conflict_note = models.Note()
        conflict_note.from_api(note_ttype, self.session)
        conflict_note.guid = ''
        conflict_note.action = const.ACTION_CONFLICT
        conflict_note.conflict_parent_id = note.id
        self.session.add(conflict_note)
        self.session.commit()

    def _remove_notes(self):
        """Remove not exists notes"""
        if self._exists:
            q = ((~models.Note.id.in_(self._exists) |
                ~models.Note.conflict_parent_id.in_(self._exists)) &
                ~models.Note.action.in_((
                    const.ACTION_NOEXSIST, const.ACTION_CREATE,
                    const.ACTION_CHANGE, const.ACTION_CONFLICT)))
        else:
            q = (~models.Note.action.in_((
                    const.ACTION_NOEXSIST, const.ACTION_CREATE,
                    const.ACTION_CHANGE, const.ACTION_CONFLICT)))
        self.session.query(models.Note).filter(q).delete(
            synchronize_session='fetch')
        self.session.commit()

    def _receive_resources(self, note, note_ttype):
        """Receive note resources"""
        resources_ids = []

        for resource_ttype in note_ttype.resources or []:
            try:
                resource = self.session.query(models.Resource).filter(
                    models.Resource.guid == resource_ttype.guid,
                ).one()
                resources_ids.append(resource.id)
                if resource.hash != binascii.b2a_hex(
                    resource_ttype.data.bodyHash,
                ):
                    resource.from_api(resource_ttype)
            except NoResultFound:
                resource = models.Resource(
                    guid=resource_ttype.guid,
                    note_id=note.id,
                )
                resource.from_api(resource_ttype)
                self.session.add(resource)
                self.session.commit()
                resources_ids.append(resource.id)

        return resources_ids

    def _remove_resources(self, note, resources_ids):
        """Remove non exists resources"""
        self.session.query(models.Resource).filter(
            ~models.Resource.id.in_(resources_ids)
            & (models.Resource.note_id == note.id)
        ).delete(synchronize_session='fetch')
        self.session.commit()

    def _check_sharing_information(self, note, note_ttype):
        """Check actual sharing information"""
        if not (
            note_ttype.attributes.shareDate or note.share_status in (
                const.SHARE_NONE, const.SHARE_NEED_SHARE,
            )
        ):
            self._stop_sharing_note(note)
        elif not (
            note_ttype.attributes.shareDate == note.share_date
            or note.share_status in (
                const.SHARE_NEED_SHARE, const.SHARE_NEED_STOP,
            )
        ):
            self._share_note(note, note_ttype.attributes.shareDate)
