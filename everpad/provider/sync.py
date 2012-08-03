import sys
sys.path.append('../..')
from PySide.QtCore import QThread, Slot
from evernote.edam.type.ttypes import Note, Notebook, Tag, NoteSortOrder
from evernote.edam.notestore.ttypes import NoteFilter
from sqlalchemy.orm.exc import NoResultFound
from evernote.edam.limits.constants import (
    EDAM_NOTE_TITLE_LEN_MAX, EDAM_NOTE_CONTENT_LEN_MAX,
    EDAM_TAG_NAME_LEN_MAX, EDAM_NOTEBOOK_NAME_LEN_MAX,
    EDAM_USER_NOTES_MAX,
)
from everpad.provider.tools import (
    ACTION_NONE, ACTION_CREATE,
    ACTION_CHANGE, ACTION_DELETE,
    get_db_session, get_auth_token,
    get_note_store,
)
from everpad.provider import models


class SyncThread(QThread):
    """Sync notes with evernote thread"""
    def run(self):
        self.session = get_db_session()
        self.sq = self.session.query
        self.auth_token = get_auth_token()
        self.note_store = get_note_store(self.auth_token)

    @Slot()
    def perform(self):
        """Perform all sync"""
        self.local_changes()
        self.remote_changes()

    def local_changes(self):
        """Send local changes to evernote server"""
        self.notebooks_local()
        self.tags_local()
        self.notes_local()
        self.session.commit()

    def remote_changes(self):
        """Receive remote changes from evernote"""
        self.notebooks_remote()
        self.tags_remote()
        self.notes_remote()
        self.session.commit()

    def notebooks_local(self):
        """Send local notebooks changes to server"""
        for notebook in self.sq(models.Notebook).filter(
            models.Notebook.action != ACTION_NONE,
        ):
            kwargs = dict(
                name=notebook.name[:EDAM_NOTEBOOK_NAME_LEN_MAX].strip().encode('utf8'),
                defaultNotebook=notebook.default,
            )
            if notebook.guid:
                kwargs['guid'] = notebook.guid
            nb = Notebook(**kwargs)
            if notebook.action == ACTION_CHANGE:
                nb = self.note_store.updateNotebook(
                    self.auth_token, nb,
                )
            elif notebook.action == ACTION_CREATE:
                nb = self.note_store.createNotebook(
                    self.auth_token, nb,
                )
                notebook.guid = nb.guid
            notebook.action = ACTION_NONE

    def tags_local(self):
        """Send loacl tags changes to server"""
        for tag in self.sq(models.Tag).filter(
            models.Tag.action != ACTION_NONE,
        ):
            kwargs = dict(
                name=tag.name[:EDAM_TAG_NAME_LEN_MAX].strip().encode('utf8'),
            )
            if tag.guid:
                kwargs['guid'] = tag.guid
            tg = Tag(**kwargs)
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

    def notes_local(self):
        """Send loacl notes changes to server"""
        for note in self.sq(models.Note).filter(
            models.Note.action != ACTION_NONE,
        ):
            kwargs = dict(
                title=note.title[:EDAM_NOTE_TITLE_LEN_MAX].strip().encode('utf8'),
                content= (u"""
                    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                    <en-note>%s</en-note>
                """ % note.content[:EDAM_NOTE_CONTENT_LEN_MAX]).strip().encode('utf8'),
                tagGuids=map(
                    lambda tag: tag.guid, note.tags,
                ),
            )
            if note.notebook:
                kwargs['notebookGuid'] = note.notebook.guid
            if note.guid:
                kwargs['guid'] = note.guid
            nt = Note(**kwargs)
            if note.action == ACTION_CHANGE:
                nt = self.note_store.updateNote(self.auth_token, nt)
            elif note.action == ACTION_CREATE:
                nt = self.note_store.createNote(self.auth_token, nt)
                note.guid = nt.guid
            elif note.action == ACTION_DELETE:
                self.note_store.deleteNote(self.auth_token, nt.guid)
                self.session.delete(note)
            note.action = ACTION_NONE

    def notebooks_remote(self):
        """Receive notebooks from server"""
        notebooks_ids = []
        for notebook in self.note_store.listNotebooks(self.auth_token):
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
                notebooks_ids.append(nb.id)
        if len(notebooks_ids):
            self.sq(models.Notebook).filter(
                ~models.Notebook.id.in_(notebooks_ids),
            ).delete(synchronize_session='fetch')

    def tags_remote(self):
        """Receive tags from server"""
        tags_ids = []
        for tag in self.note_store.listTags(self.auth_token):
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
                tags_ids.append(tg.id)
        if len(tags_ids):
            self.sq(models.Tag).filter(
                ~models.Tag.id.in_(tags_ids)
            ).delete(synchronize_session='fetch')

    def notes_remote(self):
        """Receive notes from server"""
        notes_ids = []
        for note in self.note_store.findNotes(self.auth_token, NoteFilter(
            order=NoteSortOrder.UPDATED,
            ascending=False,
        ), 0, EDAM_USER_NOTES_MAX).notes:  # TODO: think about more than 100000 notes
            try:
                nt = self.sq(models.Note).filter(
                    models.Note.guid == note.guid,
                ).one()
                notes_ids.append(nt.id)
                if nt.updated > note.updated:
                    note.content = self.note_store.getNoteContent(
                        self.auth_token, note.guid,
                    )
                    nt.from_api(note, self.sq)
            except NoResultFound:
                note.content = self.note_store.getNoteContent(
                    self.auth_token, note.guid,
                )
                nt = models.Note(guid=note.guid)
                nt.from_api(note, self.sq)
                self.session.add(nt)
                notes_ids.append(nt.id)
        if len(notes_ids):
            self.sq(models.Note).filter(
                ~models.Note.id.in_(notes_ids)
            ).delete(synchronize_session='fetch')        
