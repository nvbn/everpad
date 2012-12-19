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
    EDAM_USER_NOTES_MAX,
)
from evernote.edam.error.ttypes import EDAMUserException
from everpad.provider.tools import (
    ACTION_NONE, ACTION_CREATE,
    ACTION_CHANGE, ACTION_DELETE,
    get_db_session, get_note_store,
    ACTION_NOEXSIST, ACTION_CONFLICT,
)
from everpad.tools import get_auth_token, sanitize, clean
from everpad.provider import models
from everpad.const import (
    STATUS_NONE, STATUS_SYNC, DEFAULT_SYNC_DELAY,
    SYNC_STATE_START, SYNC_STATE_NOTEBOOKS_LOCAL,
    SYNC_STATE_TAGS_LOCAL, SYNC_STATE_NOTES_LOCAL, 
    SYNC_STATE_NOTEBOOKS_REMOTE, SYNC_STATE_TAGS_REMOTE, 
    SYNC_STATE_NOTES_REMOTE, SYNC_STATE_FINISH,
)
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime
import binascii
import time
import socket
SYNC_MANUAL = -1


class SyncThread(QThread):
    """Sync notes with evernote thread"""
    force_sync_signal = Signal()
    sync_state_changed = Signal(int)
    data_changed = Signal()

    def __init__(self, app, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.app = app
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
            if notebook.guid:
                kwargs['guid'] = notebook.guid
            nb = Notebook(**kwargs)
            if notebook.action == ACTION_CHANGE:
                while True:
                    try:
                        nb = self.note_store.updateNotebook(
                            self.auth_token, nb,
                        )
                        break
                    except EDAMUserException, e:
                        notebook.name = notebook.name + '*'  # shit, but work
                        print e
            elif notebook.action == ACTION_CREATE:
                nb = self.note_store.createNotebook(
                    self.auth_token, nb,
                )
                notebook.guid = nb.guid
            elif notebook.action == ACTION_DELETE and False:  # not allowed for app now
                try:
                    self.note_store.expungeNotebook(
                        self.auth_token, notebook.guid,
                    )
                    self.session.delete(notebook)
                except EDAMUserException, e:
                    print e
            notebook.action = ACTION_NONE
        self.session.commit()

    def tags_local(self):
        """Send loacl tags changes to server"""
        for tag in self.sq(models.Tag).filter(
            models.Tag.action != ACTION_NONE,
        ):
            self.app.log('Tag %s local' % tag.name)
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
        """Send loacl notes changes to server"""
        for note in self.sq(models.Note).filter(and_(
            models.Note.action != ACTION_NONE,
            models.Note.action != ACTION_NOEXSIST,
        )):
            self.app.log('Note %s local' % note.title)
            content = (u"""
                    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                    <en-note>%s</en-note>
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
            try:
                next_action = ACTION_NONE
                if note.action == ACTION_CHANGE:
                    nt.resources = self._resources_for_note(note)
                    nt = self.note_store.updateNote(self.auth_token, nt)
                elif note.action == ACTION_CREATE:
                    nt.resources = self._resources_for_note(note)
                    nt = self.note_store.createNote(self.auth_token, nt)
                    note.guid = nt.guid
                elif note.action == ACTION_DELETE:
                    self.note_store.deleteNote(self.auth_token, nt.guid)
                    self.session.delete(note)
            except EDAMUserException as e:
                next_action = note.action
                self.app.log('Note %s failed' % note.title)
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
        if len(notebooks_ids):
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
        if len(tags_ids):
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
                        nt = models.Note()
                    nt.from_api(note, self.session)
                    if conflict:
                        nt.guid = ''
                        nt.id = None
                        nt.action = ACTION_CONFLICT
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
        if len(notes_ids):
            ids = filter(lambda id: id not in notes_ids, map(
                lambda note: note.id, self.sq(models.Note).all(),
            ))
            if len(ids):
                self.sq(models.Note).filter(and_(
                    models.Note.id.in_(ids),
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
        if len(resources_ids):
            self.sq(models.Resource).filter(and_(
                ~models.Resource.id.in_(resources_ids),
                models.Resource.note_id == note_model.id,
            )).delete(synchronize_session='fetch')        
        self.session.commit()
