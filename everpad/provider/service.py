import sys
sys.path.append('../..')
from everpad.provider.models import (
    Note, Notebook, Tag, Resource, Place,
    ACTION_CHANGE, ACTION_CREATE, ACTION_DELETE,
    ACTION_NOEXSIST,
)
from everpad.provider.tools import get_db_session
from sqlalchemy import or_, and_, func
from sqlalchemy.orm.exc import NoResultFound
from dbus.exceptions import DBusException
from PySide.QtCore import Signal, QObject, Qt
import everpad.basetypes as btype
from everpad.const import STATUS_NONE, STATUS_SYNC, DEFAULT_SYNC_DELAY
import dbus
import dbus.service
import time


class ProviderServiceQObject(QObject):
    authenticate_signal = Signal(str)
    remove_authenticate_signal = Signal()


class ProviderService(dbus.service.Object):
    def __init__(self, app, *args, **kwargs):
        super(ProviderService, self).__init__(*args, **kwargs)
        self.qobject = ProviderServiceQObject()
        self.app = app

    @property
    def session(self):
        if not hasattr(self, '_session'):
            self._session = get_db_session()
            Note.session = self._session   # shit shit
        return self._session

    @property
    def sq(self):
        if not hasattr(self, '_sq'):
            self._sq = self.session.query
        return self._sq

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature=btype.Note.signature,
    )
    def get_note(self, id):
        try:
            return btype.Note.from_obj(self.sq(Note).filter(
                and_(Note.id == id, Note.action != ACTION_DELETE),
            ).one()).struct
        except NoResultFound:
            raise DBusException('Note not found')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='saiaiiii',
        out_signature='a%s' % btype.Note.signature,
    )
    def find_notes(self, words, notebooks, tags, place,
        limit=100, order=btype.Note.ORDER_UPDATED,
    ):
        filters = []
        if words:
            words = '%' + words.replace(' ', '%') + '%'
            filters.append(or_(  # TODO: use xapian
                Note.title.like(words),
                Note.content.like(words),
                Note.tags.any(Tag.name.like(words)),
                Note.notebook.has(Notebook.name.like(words)),
            ))
        if notebooks:
            filters.append(
                Note.notebook_id.in_(notebooks),
            )
        if tags:
            filters.append(
                Note.tags.any(Tag.id.in_(tags)),
            )
        if place:
            filters.append(
                Note.place_id == place,
            )
        qs = self.sq(Note).filter(and_(
            Note.action != ACTION_DELETE,
            Note.action != ACTION_NOEXSIST,
        *filters)).order_by({
            btype.Note.ORDER_TITLE: Note.title,
            btype.Note.ORDER_UPDATED: Note.updated,
            btype.Note.ORDER_TITLE_DESC: Note.title.desc(),
            btype.Note.ORDER_UPDATED_DESC: Note.updated.desc(),
        }[order]).limit(limit)
        return map(lambda note: btype.Note.from_obj(note).struct, qs.all())

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='a%s' % btype.Notebook.signature,
    )
    def list_notebooks(self):
        return map(lambda notebook:
            btype.Notebook.from_obj(notebook).struct,
        self.sq(Notebook).filter(Notebook.action != ACTION_DELETE).order_by(Notebook.name))

    @dbus.service.method(
        "com.everpad.Provider", in_signature='iii',
        out_signature='a%s' % btype.Note.signature,
    )
    def list_notebook_notes(self, notebook_id, limit=100, order=btype.Note.ORDER_UPDATED):
        filters = [Note.action != ACTION_DELETE, Note.action != ACTION_NOEXSIST]
        if notebook_id:
            filters.append(Note.notebook_id == notebook_id)
        qs = self.sq(Note).filter(and_(*filters)).order_by({
            btype.Note.ORDER_TITLE: Note.title,
            btype.Note.ORDER_UPDATED: Note.updated,
            btype.Note.ORDER_TITLE_DESC: Note.title.desc(),
            btype.Note.ORDER_UPDATED_DESC: Note.updated.desc(),
        }[order]).limit(limit)
        return map(lambda note: btype.Note.from_obj(note).struct, qs.all())

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature=btype.Notebook.signature,
    )
    def get_notebook(self, id):
        try:
            return btype.Notebook.from_obj(self.sq(Notebook).filter(
                Notebook.id == id,
            ).one()).struct
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='i',
    )
    def get_notebook_notes_count(self, id):
        return self.sq(Note).filter(
            Note.notebook_id == id,
        ).count()

    @dbus.service.method(
        "com.everpad.Provider", in_signature=btype.Notebook.signature,
        out_signature=btype.Notebook.signature,
    )
    def update_notebook(self, notebook_struct):
        try:
            notebook = btype.Notebook.from_tuple(notebook_struct)
            nb = self.sq(Notebook).filter(
                Notebook.id == notebook.id,
            ).one()
            if self.sq(Notebook).filter(and_(
                Notebook.id != notebook.id,
                Notebook.name == notebook.name,
            )).count():
                raise DBusException(
                    'Notebook with this name already exist',
                )
            nb.action = ACTION_CHANGE
            self.session.commit()
            notebook.give_to_obj(nb)
            return btype.Notebook.from_obj(nb).struct
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='b',
    )
    def delete_notebook(self, id):
        try:
            self.sq(Notebook).filter(
                Notebook.id == id,
            ).one().action = ACTION_DELETE
            self.session.commit()
            return True
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='a%s' % btype.Tag.signature,
    )
    def list_tags(self):
        return map(lambda tag:
            btype.Tag.from_obj(tag).struct,
        self.sq(Tag).all())

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature=btype.Note.signature,
        out_signature=btype.Note.signature,
    )
    def create_note(self, data):
        note = Note(
            action=ACTION_NOEXSIST,
        )
        btype.Note.from_tuple(data).give_to_obj(note)
        note.id = None
        note.updated = int(time.time() * 1000)
        note.created = int(time.time() * 1000)
        self.session.add(note)
        self.session.commit()
        return btype.Note.from_obj(note).struct

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature=btype.Note.signature,
        out_signature=btype.Note.signature,
    )
    def update_note(self, note):
        received_note = btype.Note.from_tuple(note)
        try:
            note = self.sq(Note).filter(
                Note.id == received_note.id,
            ).one()
        except NoResultFound:
            raise DBusException('Note not found')
        received_note.give_to_obj(note)
        if note.action == ACTION_NOEXSIST:
            note.action = ACTION_CREATE
        elif note.action != ACTION_CREATE:
            note.action = ACTION_CHANGE
        note.updated = int(time.time() * 1000)
        self.session.commit()
        return btype.Note.from_obj(note).struct

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='%sa%s' % (
            btype.Note.signature,
            btype.Resource.signature,
        ), out_signature='b',
    )
    def update_note_resources(self, note, resources):
        received_note = btype.Note.from_tuple(note)
        try:
            note = self.sq(Note).filter(
                Note.id == received_note.id,
            ).one()
        except NoResultFound:
            raise DBusException('Note not found')
        self.sq(Resource).filter(
            Resource.note_id == note.id,
        ).delete()
        for res_struct in resources:
            res = Resource(
                action=ACTION_CREATE,
                note_id=note.id,
            )
            btype.Resource.from_tuple(res_struct).give_to_obj(res)
            res.id = None
            self.session.add(res)
        if note.action != ACTION_CREATE:
            note.action = ACTION_CHANGE
        self.session.commit()
        return btype.Note.from_obj(note).struct

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='b',
    )
    def delete_note(self, id):
        try:
            self.sq(Note).filter(Note.id == id).one().action = ACTION_DELETE
            self.session.commit()
            return True
        except NoResultFound:
            raise DBusException('Note not found')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='s',
        out_signature=btype.Notebook.signature,
    )
    def create_notebook(self, name):
        if self.sq(Note).filter(
            Notebook.name == name,
        ).count():
            raise DBusException(
                'Notebook with this name already exist',
            )
        notebook = Notebook(
            action=ACTION_CREATE,
            name=name, default=False,
        )
        self.session.add(notebook)
        self.session.commit()
        return btype.Notebook.from_obj(notebook).struct

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='s', out_signature='',
    )
    def authenticate(self, token):
        self.qobject.remove_authenticate_signal.emit()
        self.qobject.authenticate_signal.emit(token)

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='',
    )
    def remove_authentication(self):
        self.qobject.remove_authenticate_signal.emit()

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='a' + btype.Resource.signature,
    )
    def get_note_resources(self, note_id):
        return map(
            lambda res: btype.Resource.from_obj(res).struct,
            self.sq(Resource).filter(and_(
                Resource.note_id == note_id,
                Resource.action != ACTION_DELETE,
            ))
        )

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='a%s' % btype.Place.signature,
    )
    def list_places(self):
        place = map(lambda place:
            btype.Place.from_obj(place).struct,
        self.sq(Place).all())
        return place

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='i',
    )
    def get_status(self):
        return self.app.sync_thread.status

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='s',
    )
    def get_last_sync(self):
        return self.app.sync_thread.last_sync.strftime('%H:%M')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='',
    )
    def sync(self):
        if self.app.sync_thread.status != STATUS_SYNC:
            self.app.sync_thread.force_sync()
        return

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='',
    )
    def set_sync_delay(self, delay):
        self.app.settings.setValue('sync_delay', str(delay))
        self.app.sync_thread.update_timer()

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='i',
    )
    def get_sync_delay(self):
        return int(self.app.settings.value('sync_delay') or 0) or DEFAULT_SYNC_DELAY

    @dbus.service.signal(
        'com.everpad.provider', signature='i',
    )
    def sync_state_changed(self, state):
        return
