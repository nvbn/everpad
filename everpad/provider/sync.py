import sys
sys.path.append('../..')
from PySide.QtCore import QThread, Slot, QTimer, Signal, QWaitCondition, QMutex
from evernote.edam.type.ttypes import (
    Note, Notebook, Tag, NoteSortOrder,
    Resource, Data, ResourceAttributes,
)
from evernote.edam.notestore.ttypes import NoteFilter
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_
from evernote.edam.limits.constants import (
    EDAM_NOTE_TITLE_LEN_MAX, EDAM_NOTE_CONTENT_LEN_MAX,
    EDAM_TAG_NAME_LEN_MAX, EDAM_NOTEBOOK_NAME_LEN_MAX,
    EDAM_NOTEBOOK_STACK_LEN_MAX,
    EDAM_USER_NOTES_MAX, EDAM_TAG_NAME_REGEX,
    EDAM_NOTEBOOK_NAME_REGEX,
)
from evernote.edam.error.ttypes import EDAMUserException
from everpad.provider.tools import (
    ACTION_NONE, ACTION_CREATE,
    ACTION_CHANGE, ACTION_DELETE,
    get_db_session, get_note_store,
    ACTION_NOEXSIST, ACTION_CONFLICT,
    get_auth_token, get_user_store,
    ACTION_DUPLICATE,
)
from everpad.provider.exceptions import TTypeValidationFailed
from everpad.specific import AppClass
from everpad.tools import sanitize
from everpad.provider import models
from everpad.const import (
    STATUS_NONE, STATUS_SYNC, DEFAULT_SYNC_DELAY,
    SYNC_STATE_START, SYNC_STATE_NOTEBOOKS_LOCAL,
    SYNC_STATE_TAGS_LOCAL, SYNC_STATE_NOTES_LOCAL,
    SYNC_STATE_NOTEBOOKS_REMOTE, SYNC_STATE_TAGS_REMOTE,
    SYNC_STATE_NOTES_REMOTE, SYNC_STATE_FINISH,
    SYNC_STATE_SHARE, SYNC_STATE_STOP_SHARE,
)
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import binascii
import time
import socket
import regex
SYNC_MANUAL = -1


class BaseSync(object):
    """Base class for sync"""

    def __init__(self, auth_token, session, note_store, user_store):
        """Set shortcuts"""
        self.auth_token = auth_token
        self.session = session
        self.note_store = note_store
        self.user_store = user_store
        self.app = AppClass.instance()


class PushNotebook(BaseSync):
    """Notebook sync"""

    def push(self):
        """Push notebook changes to server"""
        for notebook in self.session.query(models.Notebook).filter(
            models.Notebook.action != ACTION_NONE,
        ):
            self.app.log('Notebook %s local' % notebook.name)

            try:
                notebook_ttype = self._create_ttype(notebook)
            except TTypeValidationFailed:
                self.app.log('notebook %s skipped' % notebook.name)
                notebook.action = ACTION_NONE
                continue

            if notebook.action == ACTION_CREATE:
                self._push_new_notebook(notebook, notebook_ttype)
            elif notebook.action == ACTION_CHANGE:
                self._push_changed_notebook(notebook, notebook_ttype)

        self.session.commit()
        self._merge_duplicates()

    def _create_ttype(self, notebook):
        """Create notebook ttype"""
        kwargs = dict(
            name=notebook.name[
                :EDAM_NOTEBOOK_NAME_LEN_MAX
            ].strip().encode('utf8'),
            defaultNotebook=notebook.default,
        )

        if notebook.stack:
            kwargs['stack'] = notebook.stack[
                :EDAM_NOTEBOOK_STACK_LEN_MAX
            ].strip().encode('utf8')

        if not regex.search(EDAM_NOTEBOOK_NAME_REGEX, notebook.name):
            raise TTypeValidationFailed()

        if notebook.guid:
            kwargs['guid'] = notebook.guid

        return Notebook(**kwargs)

    def _push_new_notebook(self, notebook, notebook_ttype):
        """Push new notebook to server"""
        try:
            notebook_ttype = self.note_store.createNotebook(
                self.auth_token, notebook_ttype,
            )
            notebook.guid = notebook_ttype.guid
            notebook.action = ACTION_NONE
        except EDAMUserException:
            notebook.action = ACTION_DUPLICATE
            self.app.log('Duplicate %s' % notebook_ttype.name)

    def _push_changed_notebook(self, notebook, notebook_ttype):
        """Push changed notebook"""
        try:
            notebook_ttype = self.note_store.updateNotebook(
                self.auth_token, notebook_ttype,
            )
            notebook.action = ACTION_NONE
        except EDAMUserException:
            notebook.action = ACTION_DUPLICATE
            self.app.log('Duplicate %s' % notebook_ttype.name)

    def _merge_duplicates(self):
        """Merge and remove duplicates"""
        for notebook in self.session.query(models.Notebook).filter(
            models.Notebook.action == ACTION_DUPLICATE,
        ):
            try:
                original = self.session.query(models.Notebook).filter(
                    (models.Notebook.action != ACTION_DUPLICATE)
                    & (models.Notebook.name == notebook.name)
                ).one()
            except NoResultFound:
                original = self.session.query(models.Notebook).filter(
                    models.Notebook.default == True,
                ).one()

            for note in self.session.query(models.Note).filter(
                models.Note.notebook_id == notebook.id,
            ):
                note.notebook = original

            self.session.delete(notebook)
        self.session.commit()


class PullNotebook(BaseSync):
    """Pull notebook from server"""

    def __init__(self, *args, **kwargs):
        super(PullNotebook, self).__init__(*args, **kwargs)
        self._exists = []

    def pull(self):
        """Receive notebooks from server"""
        for notebook_ttype in self.note_store.listNotebooks(self.auth_token):
            self.app.log('Notebook %s remote' % notebook_ttype.name)
            try:
                notebook = self._update_notebook(notebook_ttype)
            except NoResultFound:
                notebook = self._create_notebook(notebook_ttype)
            self._exists.append(notebook.id)

        self.session.commit()
        self._remove_notebooks()

    def _create_notebook(self, notebook_ttype):
        """Create notebook from ttype"""
        notebook = models.Notebook(guid=notebook_ttype.guid)
        notebook.from_api(notebook_ttype)
        self.session.add(notebook)
        self.session.commit()
        return notebook

    def _update_notebook(self, notebook_ttype):
        """Try to update notebook from ttype"""
        notebook = self.session.query(models.Notebook).filter(
            models.Notebook.guid == notebook_ttype.guid,
        ).one()
        if notebook.service_updated < notebook_ttype.serviceUpdated:
            notebook.from_api(notebook_ttype)
        return notebook

    def _remove_notebooks(self):
        """Remove not received notebooks"""
        self.session.query(models.Notebook).filter(
            ~models.Notebook.id.in_(self._exists)
            & (models.Notebook.action != ACTION_CREATE)
            & (models.Notebook.action != ACTION_CHANGE)
        ).delete(synchronize_session='fetch')


class PushTag(BaseSync):
    """Push tags to server"""

    def push(self):
        """Push tags"""
        for tag in self.session.query(models.Tag).filter(
            models.Tag.action != ACTION_NONE,
        ):
            self.app.log('Tag %s local' % tag.name)

            try:
                tag_ttype = self._create_ttype(tag)
            except TTypeValidationFailed:
                tag.action = ACTION_NONE
                self.app.log('tag %s skipped' % tag.name)
                continue

            if tag.action == ACTION_CREATE:
                self._push_new_tag(tag, tag_ttype)
            elif tag.action == ACTION_CHANGE:
                self._push_changed_tag(tag, tag_ttype)

        self.session.commit()

    def _create_ttype(self, tag):
        """Create tag ttype"""
        if not regex.search(EDAM_TAG_NAME_REGEX, tag.name):
            raise TTypeValidationFailed()

        kwargs = dict(
            name=tag.name[:EDAM_TAG_NAME_LEN_MAX].strip().encode('utf8'),
        )

        if tag.guid:
            kwargs['guid'] = tag.guid

        return Tag(**kwargs)

    def _push_new_tag(self, tag, tag_ttype):
        """Push new tag"""
        try:
            tag_ttype = self.note_store.createTag(
                self.auth_token, tag_ttype,
            )
            tag.guid = tag_ttype.guid
            tag.action = ACTION_NONE
        except EDAMUserException as e:
            self.app.log(e)

    def _push_changed_tag(self, tag, tag_ttype):
        """Push changed tag"""
        try:
            self.note_store.updateTag(
                self.auth_token, tag_ttype,
            )
            tag.action = ACTION_NONE
        except EDAMUserException as e:
            self.app.log(e)


class PullTag(BaseSync):
    """Pull tags from server"""

    def __init__(self, *args, **kwargs):
        super(PullTag, self).__init__(*args, **kwargs)
        self._exists = []

    def pull(self):
        """Pull tags from server"""
        for tag_ttype in self.note_store.listTags(self.auth_token):
            self.app.log('Tag %s remote' % tag_ttype.name)
            try:
                tag = self._update_tag(tag_ttype)
            except NoResultFound:
                tag = self._create_tag(tag_ttype)
            self._exists.append(tag.id)

        self.session.commit()
        self._remove_tags()

    def _create_tag(self, tag_ttype):
        """Create notebook from server"""
        tag = models.Tag(guid=tag_ttype.guid)
        tag.from_api(tag_ttype)
        self.session.add(tag)
        self.session.commit()
        return tag

    def _update_tag(self, tag_ttype):
        """Update tag if exists"""
        tag = self.session.query(models.Tag).filter(
            models.Tag.guid == tag_ttype.guid,
        ).one()
        if tag.name != tag_ttype.name.decode('utf8'):
            tag.from_api(tag_ttype)
        return tag

    def _remove_tags(self):
        """Remove not exist tags"""
        self.session.query(models.Tag).filter(
            ~models.Tag.id.in_(self._exists)
            & (models.Tag.action != ACTION_CREATE)
        ).delete(synchronize_session='fetch')


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
            note.share_status = models.SHARE_SHARED
        except EDAMUserException as e:
            note.share_status = models.SHARE_NONE
            self.app.log('Sharing note %s failed' % note.title)
            self.app.log(e)

    def _stop_sharing_note(self, note):
        """Stop sharing note"""
        note.share_status = models.SHARE_NONE
        note.share_date = None
        note.share_url = None
        self.session.commit()


class PushNote(BaseSync, ShareNoteMixin):
    """Push note to remote server"""

    def push(self):
        """Push note to remote server"""
        for note in self.session.query(models.Note).filter(
            ~models.Note.action.in_((
                ACTION_NONE, ACTION_NOEXSIST, ACTION_CONFLICT,
            ))
        ):
            self.app.log('Note %s local' % note.title)
            note_ttype = self._create_ttype(note)

            if note.action == ACTION_CREATE:
                self._push_new_note(note, note_ttype)
            elif note.action == ACTION_CHANGE:
                self._push_changed_note(note, note_ttype)
            elif note.action == ACTION_DELETE:
                self._delete_note(note, note_ttype)

            if note.share_status == models.SHARE_NEED_SHARE:
                self._share_note(note)
            elif note.share_status == models.SHARE_NEED_STOP:
                self._stop_sharing_note(note)

        self.session.commit()

    def _create_ttype(self, note):
        """Create ttype for note"""
        kwargs = dict(
            title=note.title[:EDAM_NOTE_TITLE_LEN_MAX].strip().encode('utf8'),
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

        return Note(**kwargs)

    def _prepare_resources(self, note):
        """Prepare note resources"""
        return map(
            lambda resource: Resource(
                noteGuid=note.guid,
                data=Data(body=open(resource.file_path).read()),
                mime=resource.mime,
                attributes=ResourceAttributes(
                    fileName=resource.file_name.encode('utf8'),
                ),
            ), self.session.query(models.Resource).filter(
                (models.Resource.note_id == note.id)
                & (models.Resource.action != models.ACTION_DELETE)
            ),
        )

    def _prepare_content(self, content):
        """Prepare content"""
        enml_content = (u"""
            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
            <en-note>{}</en-note>d
        """.format(sanitize(
            html=content[:EDAM_NOTE_CONTENT_LEN_MAX]
        ))).strip().encode('utf8')

        soup = BeautifulStoneSoup(enml_content, selfClosingTags=[
            'img', 'en-todo', 'en-media', 'br', 'hr',
        ])

        return soup.prettify()

    def _push_new_note(self, note, note_ttype):
        """Push new note to remote"""
        try:
            note_ttype = self.note_store.createNote(self.auth_token, note_ttype)
            note.guid = note_ttype.guid
        except EDAMUserException as e:
            note.action = ACTION_NONE
            self.app.log('Note %s failed' % note.title)
            self.app.log(e)
        finally:
            note.action = ACTION_NONE

    def _push_changed_note(self, note, note_ttype):
        """Push changed note to remote"""
        try:
            self.note_store.updateNote(self.auth_token, note_ttype)
        except EDAMUserException as e:
            self.app.log('Note %s failed' % note.title)
            self.app.log(e)
        finally:
            note.action = ACTION_NONE

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
            self.app.log('Note %s remote' % note_ttype.title)
            try:
                note = self._update_note(note_ttype)
            except NoResultFound:
                note = self._create_note(note_ttype)
            self._exists.append(note.id)

            self._check_sharing_information(note, note_ttype)

            resource_ids = self._receive_resources(note, note_ttype)
            self._remove_resources(note, resource_ids)

        self.session.commit()
        self._remove_notes()

    def _get_all_notes(self):
        """Iterate all notes"""
        offset = 0

        while True:
            note_list = self.note_store.findNotes(self.auth_token, NoteFilter(
                order=NoteSortOrder.UPDATED,
                ascending=False,
            ), offset, EDAM_USER_NOTES_MAX)

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
            if note.action == ACTION_CHANGE:
                self._create_conflict(note, note_ttype)
            else:
                note.from_api(note_ttype, self.session)
        return note

    def _create_conflict(self, note, note_ttype):
        """Create conflict note"""
        conflict_note = models.Note()
        conflict_note.from_api(note_ttype, self.session)
        conflict_note.guid = ''
        conflict_note.action = ACTION_CONFLICT
        conflict_note.conflict_parent_id = note.id
        self.session.add(conflict_note)
        self.session.commit()

    def _remove_notes(self):
        """Remove not exists notes"""
        self.session.query(models.Note).filter((
            ~models.Note.id.in_(self._exists)
            | ~models.Note.conflict_parent_id.in_(self._exists)
        ) & ~models.Note.action.in_((
            ACTION_NOEXSIST, ACTION_CREATE,
            ACTION_CHANGE, ACTION_CONFLICT,
        ))).delete(synchronize_session='fetch')
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
                models.SHARE_NONE, models.SHARE_NEED_SHARE,
            )
        ):
            self._stop_sharing_note(note)
        elif not (
            note_ttype.attributes.shareDate == note.share_date
            or note.share_status in (
                models.SHARE_NEED_SHARE, models.SHARE_NEED_STOP,
            )
        ):
            self._share_note(note, note_ttype.attributes.shareDate)


class SyncAgent(object):
    """Split agent for latest backends support"""
    @property
    def shard_id(self):
        """User sharId"""
        if not hasattr(self, '_shard_id'):
            user_store = get_user_store()
            user = user_store.getUser(self.auth_token)
            self._shard_id = user.shardId
        return self._shard_id

    def _iter_all_notes(self):
        """Iterate all notes"""
        offset = 0
        while True:
            note_list = self.note_store.findNotes(self.auth_token, NoteFilter(
                order=NoteSortOrder.UPDATED,
                ascending=False,
            ), offset, EDAM_USER_NOTES_MAX)
            for note in note_list.notes:
                yield note
            offset = note_list.startIndex + len(note_list.notes)
            if note_list.totalNotes - offset <= 0:
                break

    def _need_to_update(self):
        """Check need for update notes"""
        update_count = self.note_store.getSyncState(self.auth_token).updateCount
        reason = update_count != self.update_count
        self.update_count = update_count
        return reason

    def notebooks_local(self):
        """Send local notebooks changes to server"""
        for notebook in self.sq(models.Notebook).filter(
            models.Notebook.action != ACTION_NONE,
        ):
            self.app.log('Notebook %s local' % notebook.name)
            kwargs = dict(
                name=notebook.name[:EDAM_NOTEBOOK_NAME_LEN_MAX].strip().encode('utf8'),
                defaultNotebook=notebook.default,
            )
            if notebook.stack:
                kwargs['stack'] = notebook.stack[:EDAM_NOTEBOOK_STACK_LEN_MAX].strip().encode('utf8')
            if not regex.search(EDAM_NOTEBOOK_NAME_REGEX, notebook.name):
                self.app.log('notebook %s skipped' % notebook.name)
                notebook.action = ACTION_NONE
                continue  # just ignore it
            if notebook.guid:
                kwargs['guid'] = notebook.guid
            nb = Notebook(**kwargs)
            if notebook.action == ACTION_CHANGE:
                try:
                    nb = self.note_store.updateNotebook(
                        self.auth_token, nb,
                    )
                    notebook.action = ACTION_NONE
                except EDAMUserException:
                    notebook.action = ACTION_DUPLICATE
                    self.app.log('Duplicate %s' % nb.name)
            elif notebook.action == ACTION_CREATE:
                try:
                    nb = self.note_store.createNotebook(
                        self.auth_token, nb,
                    )
                    notebook.guid = nb.guid
                    notebook.action = ACTION_NONE
                except EDAMUserException:
                    notebook.action = ACTION_DUPLICATE
                    self.app.log('Duplicate %s' % nb.name)
            elif notebook.action == ACTION_DELETE and False:  # not allowed for app now
                try:
                    self.note_store.expungeNotebook(
                        self.auth_token, notebook.guid,
                    )
                    self.session.delete(notebook)
                except EDAMUserException, e:
                    self.app.log(e)
        self.session.commit()
        self.notebook_duplicates()

    def notebook_duplicates(self):
        """Merge and remove duplicates"""
        for notebook in self.sq(models.Notebook).filter(
            models.Notebook.action == ACTION_DUPLICATE,
        ):
            try:
                original = self.sq(models.Notebook).filter(and_(
                    models.Notebook.action == ACTION_DUPLICATE,
                    models.Notebook.name == notebook.name,
                )).one()
            except NoResultFound:
                original = self.sq(models.Notebook).filter(
                    models.Notebook.default == True,
                ).one()
            for note in self.sq(models.Note).filter(
                models.Note.notebook_id == notebook.id,
            ):
                note.notebook_id = original.id
            self.session.delete(notebook)
        self.session.commit()

    def tags_local(self):
        """Send local tags changes to server"""
        for tag in self.sq(models.Tag).filter(
            models.Tag.action != ACTION_NONE,
        ):
            self.app.log('Tag %s local' % tag.name)
            if not regex.search(EDAM_TAG_NAME_REGEX, tag.name):
                tag.action = ACTION_NONE
                self.app.log('tag %s skipped' % tag.name)
                continue  # just ignore it
            kwargs = dict(
                name=tag.name[:EDAM_TAG_NAME_LEN_MAX].strip().encode('utf8'),
            )
            if tag.guid:
                kwargs['guid'] = tag.guid
            tg = Tag(**kwargs)
            try:
                if tag.action == ACTION_CHANGE:
                    tg = self.note_store.updateTag(
                        self.auth_token, tg,
                    )
                elif tag.action == ACTION_CREATE:
                    tg = self.note_store.createTag(
                        self.auth_token, tg,
                    )
                    tag.guid = tg.guid
                tag.action = ACTION_NONE
            except EDAMUserException as e:
                self.app.log(e)
        self.session.commit()

    def _resources_for_note(self, note):
        return map(lambda res: Resource(
            noteGuid=note.guid,
            data=Data(body=open(res.file_path).read()),
            mime=res.mime,
            attributes=ResourceAttributes(
                fileName=res.file_name.encode('utf8'),
            ),
        ), self.sq(models.Resource).filter(and_(
            models.Resource.note_id == note.id,
            models.Resource.action != models.ACTION_DELETE,
        )))

    def notes_local(self):
        """Send local notes changes to server"""
        for note in self.sq(models.Note).filter(and_(
            models.Note.action != ACTION_NONE,
            models.Note.action != ACTION_NOEXSIST,
            models.Note.action != ACTION_CONFLICT,
        )):
            self.app.log('Note %s local' % note.title)
            content = (u"""
                    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                    <en-note>%s</en-note>d
                """ % sanitize(
                        html=note.content[:EDAM_NOTE_CONTENT_LEN_MAX]
                    )).strip().encode('utf8')
            soup = BeautifulStoneSoup(content, selfClosingTags=[
                'img', 'en-todo', 'en-media', 'br', 'hr',
            ])
            kwargs = dict(
                title=note.title[:EDAM_NOTE_TITLE_LEN_MAX].strip().encode('utf8'),
                content=soup.prettify(),
                tagGuids=map(
                    lambda tag: tag.guid, note.tags,
                ),
            )
            if note.notebook:
                kwargs['notebookGuid'] = note.notebook.guid
            if note.guid:
                kwargs['guid'] = note.guid
            nt = Note(**kwargs)
                        
            next_action = ACTION_NONE
            
            if note.action == ACTION_DELETE:
                try:
                    self.note_store.deleteNote(self.auth_token, nt.guid)
                except EDAMUserException as e:
                    self.app.log('Note %s already removed' % note.title)
                    self.app.log(e)

                self.session.delete(note)
            else:
                try:
                    if note.action == ACTION_CHANGE:
                        nt.resources = self._resources_for_note(note)
                        nt = self.note_store.updateNote(self.auth_token, nt)
                    elif note.action == ACTION_CREATE:
                        nt.resources = self._resources_for_note(note)
                        nt = self.note_store.createNote(self.auth_token, nt)
                        note.guid = nt.guid
                except EDAMUserException as e:
                    next_action = ACTION_NONE
                    self.app.log('Note %s failed' % note.title)
                    self.app.log(e)
            note.action = next_action
        self.session.commit()

    def notebooks_remote(self):
        """Receive notebooks from server"""
        notebooks_ids = []
        for notebook in self.note_store.listNotebooks(self.auth_token):
            self.app.log('Notebook %s remote' % notebook.name)
            try:
                nb = self.sq(models.Notebook).filter(
                    models.Notebook.guid == notebook.guid,
                ).one()
                notebooks_ids.append(nb.id)
                if nb.service_updated < notebook.serviceUpdated:
                    nb.from_api(notebook)
            except NoResultFound:
                nb = models.Notebook(guid=notebook.guid)
                nb.from_api(notebook)
                self.session.add(nb)
                self.session.commit()
                notebooks_ids.append(nb.id)
        ids = filter(lambda id: id not in notebooks_ids, map(
            lambda nb: nb.id, self.sq(models.Notebook).all(),
        ))
        if len(ids):
            self.sq(models.Notebook).filter(and_(
                models.Notebook.id.in_(ids),
                models.Notebook.action != ACTION_CREATE,
                models.Notebook.action != ACTION_CHANGE,
            )).delete(synchronize_session='fetch')
        self.session.commit()

    def tags_remote(self):
        """Receive tags from server"""
        tags_ids = []
        for tag in self.note_store.listTags(self.auth_token):
            self.app.log('Tag %s remote' % tag.name)
            try:
                tg = self.sq(models.Tag).filter(
                    models.Tag.guid == tag.guid,
                ).one()
                tags_ids.append(tg.id)
                if tg.name != tag.name.decode('utf8'):
                    tg.from_api(tag)
            except NoResultFound:
                tg = models.Tag(guid=tag.guid)
                tg.from_api(tag)
                self.session.add(tg)
                self.session.commit()
                tags_ids.append(tg.id)
        ids = filter(lambda id: id not in tags_ids, map(
            lambda tag: tag.id, self.sq(models.Tag).all(),
        ))
        if len(ids):
            self.sq(models.Tag).filter(and_(
                models.Tag.id.in_(ids),
                models.Tag.action != ACTION_CREATE,
            )).delete(synchronize_session='fetch')
        self.session.commit()

    def notes_remote(self):
        """Receive notes from server"""
        notes_ids = []
        for note in self.all_notes:
            self.app.log('Note %s remote' % note.title)
            try:
                nt = self.sq(models.Note).filter(
                    models.Note.guid == note.guid,
                ).one()
                notes_ids.append(nt.id)
                conflict = nt.action == ACTION_CHANGE
                if nt.updated < note.updated:
                    note = self.note_store.getNote(
                        self.auth_token, note.guid,
                        True, True, True, True,
                    )
                    if conflict:
                        parent = nt
                        nt = models.Note()
                    nt.from_api(note, self.session)
                    if conflict:
                        nt.guid = ''
                        nt.action = ACTION_CONFLICT
                        nt.conflict_parent_id = parent.id
                        self.session.add(nt)
                        self.session.commit()
                    self.note_resources_remote(note, nt)
            except NoResultFound:
                note = self.note_store.getNote(
                    self.auth_token, note.guid,
                    True, True, True, True,
                )
                nt = models.Note(guid=note.guid)
                nt.from_api(note, self.session)
                self.session.add(nt)
                self.session.commit()
                notes_ids.append(nt.id)
                self.note_resources_remote(note, nt)
            if not note.attributes.shareDate and nt.share_status not in (
                    models.SHARE_NONE, models.SHARE_NEED_SHARE,
                ):
                nt.share_status = models.SHARE_NONE
                nt.share_date = None
                nt.share_url = None
                self.session.commit()
            elif note.attributes.shareDate != nt.share_date and nt.share_status not in(
                    models.SHARE_NEED_SHARE, models.SHARE_NEED_STOP,
                ):
                self._single_note_share(nt, note.attributes.shareDate)
                self.session.commit()
        ids = filter(lambda id: id not in notes_ids, map(
            lambda note: note.id, self.sq(models.Note).all(),
        ))
        if len(ids):
            self.sq(models.Note).filter(and_(
                models.Note.id.in_(ids),
                models.Note.conflict_parent_id.in_(ids),
                models.Note.action != ACTION_NOEXSIST,
                models.Note.action != ACTION_CREATE,
                models.Note.action != ACTION_CHANGE,
                models.Note.action != ACTION_CONFLICT,
            )).delete(synchronize_session='fetch')
        self.session.commit()

    def note_resources_remote(self, note_api, note_model):
        resources_ids = []
        for resource in note_api.resources or []:
            try:
                rs = self.sq(models.Resource).filter(
                    models.Resource.guid == resource.guid,
                ).one()
                resources_ids.append(rs.id)
                if rs.hash != binascii.b2a_hex(resource.data.bodyHash):
                    rs.from_api(resource)
            except NoResultFound:
                rs = models.Resource(
                    guid=resource.guid,
                    note_id=note_model.id,
                )
                rs.from_api(resource)
                self.session.add(rs)
                self.session.commit()
                resources_ids.append(rs.id)
        self.sq(models.Resource).filter(and_(
            ~models.Resource.id.in_(resources_ids),
            models.Resource.note_id == note_model.id,
        )).delete(synchronize_session='fetch')
        self.session.commit()

    def _single_note_share(self, note, share_date=None):
        try:
            share_key = self.note_store.shareNote(self.auth_token, note.guid)
            note.share_url = "https://www.evernote.com/shard/%s/sh/%s/%s" % (
                self.shard_id, note.guid, share_key,
            )
            note.share_date = share_date or int(time.time() * 1000)
            note.share_status = models.SHARE_SHARED
        except EDAMUserException as e:
            note.share_status = models.SHARE_NONE
            self.app.log('Sharing note %s failed' % note.title)
            self.app.log(e)

    def notes_sharing(self):
        """Notes sharing"""
        for note in self.sq(models.Note).filter(
            models.Note.share_status == models.SHARE_NEED_SHARE,
        ):
            self._single_note_share(note)
        self.session.commit()

    def _single_note_stop_sharing(self, note):
        """Stop sharing single note"""
        try:
            note.share_url = None
            note.share_date = None
            note.share_status = models.SHARE_NONE
        except EDAMUserException as e:
            note.share_status = models.SHARE_SHARED
            self.app.log('Stop sharing note %s failed' % note.title)
            self.app.log(e)

    def notes_stop_sharing(self):
        """Stop sharing otes"""
        for note in self.sq(models.Note).filter(
            models.Note.share_status == models.SHARE_NEED_STOP,
        ):
            self._single_note_stop_sharing(note)
        self.session.commit()


class SyncThread(QThread, SyncAgent):
    """Sync notes with evernote thread"""
    force_sync_signal = Signal()
    sync_state_changed = Signal(int)
    data_changed = Signal()

    def __init__(self, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.app = AppClass.instance()
        self.status = STATUS_NONE
        self.last_sync = datetime.now()
        self.update_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.update_timer()
        self.wait_condition = QWaitCondition()
        self.mutex = QMutex()

    def update_timer(self):
        self.timer.stop()
        delay = int(self.app.settings.value('sync_delay') or 0) or DEFAULT_SYNC_DELAY
        if delay != SYNC_MANUAL:
            self.timer.start(delay)

    def run(self):
        self.init_db()
        self.init_network()
        while True:
            self.mutex.lock()
            self.wait_condition.wait(self.mutex)
            self.perform()
            self.mutex.unlock()
            time.sleep(1)  # prevent cpu eating

    def init_db(self):
        self.session = get_db_session()
        self.sq = self.session.query

    def init_network(self):
        while True:
            try:
                self.auth_token = get_auth_token()
                self.note_store = get_note_store(self.auth_token)
                break
            except socket.error:
                time.sleep(30)

    def force_sync(self):
        self.timer.stop()
        self.sync()
        self.update_timer()

    @Slot()
    def sync(self):
        self.wait_condition.wakeAll()

    def perform(self):
        """Perform all sync"""
        self.status = STATUS_SYNC
        self.last_sync = datetime.now()
        self.sync_state_changed.emit(SYNC_STATE_START)
        if self._need_to_update():
            self.need_to_update = True
            self.all_notes = list(self._iter_all_notes())
        try:
            if self.need_to_update:
                self.remote_changes()
            self.local_changes()
            self.sharing_changes()
        except Exception, e:  # maybe log this
            self.session.rollback()
            self.init_db()
            self.app.log(e)
        finally:
            self.sync_state_changed.emit(SYNC_STATE_FINISH)
            self.status = STATUS_NONE
            self.need_to_update = False
            self.all_notes = None
        self.data_changed.emit()

    def local_changes(self):
        """Send local changes to evernote server"""
        self.sync_state_changed.emit(SYNC_STATE_NOTEBOOKS_LOCAL)
        self.notebooks_local()
        self.sync_state_changed.emit(SYNC_STATE_TAGS_LOCAL)
        self.tags_local()
        self.sync_state_changed.emit(SYNC_STATE_NOTES_LOCAL)
        self.notes_local()

    def remote_changes(self):
        """Receive remote changes from evernote"""
        self.sync_state_changed.emit(SYNC_STATE_NOTEBOOKS_REMOTE)
        self.notebooks_remote()
        self.sync_state_changed.emit(SYNC_STATE_TAGS_REMOTE)
        self.tags_remote()
        self.sync_state_changed.emit(SYNC_STATE_NOTES_REMOTE)
        self.notes_remote()

    def sharing_changes(self):
        """Update sharing information"""
        self.sync_state_changed.emit(SYNC_STATE_SHARE)
        self.notes_sharing()
        self.sync_state_changed.emit(SYNC_STATE_STOP_SHARE)
        self.notes_stop_sharing()
