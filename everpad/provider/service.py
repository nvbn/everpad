from PySide.QtCore import Signal, QObject
from sqlalchemy import or_, and_, func
from sqlalchemy.orm.exc import NoResultFound
from dbus.exceptions import DBusException
from .. import const, basetypes as btype
from ..specific import AppClass
from . import models
from .tools import get_db_session, get_auth_token
import dbus
import dbus.service
import time


class NoteFilterer(object):
    """Create list with wiltered and sorted notes"""

    def __init__(self, session):
        self._filters = []
        self._order = None
        self.session = session

    def by_words(self, words):
        """Add filter by words"""
        if words:
            words = '%' + words.replace(' ', '%').lower() + '%'
            self._filters.append(
                func.lower(models.Note.title).like(words)
                | func.lower(models.Note.content).like(words)
                | models.Note.tags.any(
                    func.lower(models.Tag.name).like(words),
                )
                | models.Note.notebook.has(
                    func.lower(models.Notebook.name).like(words)
                )
            )
        return self

    def by_notebooks(self, notebooks):
        """Add filter by notebooks"""
        if notebooks:
            self._filters.append(
                models.Note.notebook_id.in_(notebooks),
            )
        return self

    def by_tags(self, tags):
        """Add filter by tags"""
        if tags:
            self._filters.append(
                models.Note.tags.any(models.Tag.id.in_(tags)),
            )
        return self

    def by_place(self, place):
        """Add filter by place"""
        if place:
            self._filters.append(
                models.Note.place_id == place,
            )
        return self

    def by_pinnded(self, pinnded):
        """By pinnded status"""
        if pinnded != const.NOT_PINNDED:
            self._filters.append(
                models.Note.pinnded == pinnded,
            )
        return self

    def order_by(self, order):
        """Set ordering"""
        self._order = {
            btype.Note.ORDER_TITLE: models.Note.title,
            btype.Note.ORDER_UPDATED: models.Note.updated,
            btype.Note.ORDER_TITLE_DESC: models.Note.title.desc(),
            btype.Note.ORDER_UPDATED_DESC: models.Note.updated.desc(),
        }[order]
        return self

    def all(self):
        """Get result"""
        return self.session.query(models.Note).filter(and_(
            ~models.Note.action.in_(const.DISABLED_ACTIONS),
            *self._filters
        )).order_by(self._order)


class ProviderServiceQObject(QObject):
    """Signals holder for service"""
    authenticate_signal = Signal(str)
    remove_authenticate_signal = Signal()
    terminate = Signal()


class ProviderService(dbus.service.Object):
    """DBus service for provider"""

    def __init__(self, *args, **kwargs):
        super(ProviderService, self).__init__(*args, **kwargs)
        self.qobject = ProviderServiceQObject()
        self.app = AppClass.instance()

    @property
    def session(self):
        if not hasattr(self, '_session'):
            self._session = get_db_session()
            models.Note.session = self._session   # shit shit
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
        """Get nite by id"""
        try:
            note = self.session.query(models.Note).filter(
                (models.Note.id == id)
                & (models.Note.action != const.ACTION_DELETE)
            ).one()

            return btype.Note >> note
        except NoResultFound:
            raise DBusException('models.Note not found')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='s',
        out_signature=btype.Note.signature,
    )
    def get_note_by_guid(self, guid):
        """Get note by guid"""
        try:
            note = self.session.query(models.Note).filter(
                (models.Note.guid == guid)
                & ~models.Note.action.in_(const.DISABLED_ACTIONS)
            ).one()

            return btype.Note >> note
        except NoResultFound:
            raise DBusException('Note not found')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='a{}'.format(btype.Note.signature),
    )
    def get_note_alternatives(self, id):
        """Get note conflict alternatives"""
        notes = self.session.query(models.Note).filter(
            models.Note.conflict_parent_id == id,
        ).all()
        return btype.Note.list >> notes

    @dbus.service.method(
        "com.everpad.Provider", in_signature='saiaiiiii',
        out_signature='a{}'.format(btype.Note.signature),
    )
    def find_notes(
        self, words, notebooks, tags, place,
        limit=const.DEFAULT_LIMIT, order=const.ORDER_UPDATED,
        pinnded=const.NOT_PINNDED,
    ):
        """Find notes by filters"""
        notes = btype.Note.list >> NoteFilterer(self.session)\
            .by_words(words)\
            .by_notebooks(notebooks)\
            .by_tags(tags)\
            .by_place(place)\
            .by_pinnded(pinnded)\
            .order_by(order)\
            .all()\
            .limit(limit)

        return notes

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='a{}'.format(btype.Notebook.signature),
    )
    def list_notebooks(self):
        """List available notebooks"""
        notebooks = self.session.query(models.Notebook).filter(
            models.Notebook.action != const.ACTION_DELETE,
        ).order_by(models.Notebook.name)

        return btype.Notebook.list >> notebooks

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature=btype.Notebook.signature,
    )
    def get_notebook(self, id):
        """Get notebook by id"""
        try:
            notebook = self.session.query(models.Notebook).filter(
                (models.Notebook.id == id)
                & (models.Notebook.action != const.ACTION_DELETE)
            ).one()

            return btype.Notebook >> notebook
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='i',
    )
    def get_notebook_notes_count(self, id):
        """Get count of notes in notebook"""
        return self.session.query(models.Note).filter(
            (models.Note.notebook_id == id)
            & ~models.Note.action.in_(const.DISABLED_ACTIONS)
        ).count()

    @dbus.service.method(
        "com.everpad.Provider", in_signature=btype.Notebook.signature,
        out_signature=btype.Notebook.signature,
    )
    def update_notebook(self, notebook_struct):
        """Update notebook"""
        try:
            notebook_btype = btype.Notebook << notebook_struct

            notebook = self.session.query(models.Notebook).filter(
                (models.Notebook.id == notebook_btype.id)
                & (models.Notebook.action != const.ACTION_DELETE)
            ).one()

            if self.session.query(models.Notebook).filter(
                (models.Notebook.id != notebook_btype.id)
                & (models.Notebook.name == notebook_btype.name)
            ).count():
                raise DBusException(
                    'Notebook with this name already exist',
                )

            notebook.action = const.ACTION_CHANGE
            notebook_btype.give_to_obj(notebook)
            self.session.commit()

            self.data_changed()

            return btype.Notebook >> notebook
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='b',
    )
    def delete_notebook(self, id):
        """Delete notebook"""
        try:
            notebook = self.session.query(models.Notebook).filter(
                models.Notebook.id == id,
            ).one()
            notebook.action = const.ACTION_DELETE
            self.session.commit()
            self.data_changed()
            return True
        except NoResultFound:
            raise DBusException('Notebook does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='a{}'.format(btype.Tag.signature),
    )
    def list_tags(self):
        """List all tags"""
        tags = self.session.query(models.Tag).filter(
            models.Tag.action != const.ACTION_DELETE,
        ).order_by(models.Tag.name)

        return btype.Tag.list >> tags

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='i',
    )
    def get_tag_notes_count(self, id):
        """Get count of notes with tag"""
        return self.session.query(models.Note).filter(
            models.Note.tags.any(models.Tag.id == id)
            & ~models.Note.action.in_(const.DISABLED_ACTIONS)
        ).count()

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='b',
    )
    def delete_tag(self, id):
        """Delete tag"""
        try:
            tag = self.session.query(models.Tag).filter(
                (models.Tag.id == id)
                & (models.Tag.action != const.ACTION_DELETE)
            ).one()

            tag.action = const.ACTION_DELETE

            for note in self.session.query(models.Note).filter(
                models.Note.tags.contains(tag),
            ).all():
                note.tags.remove(tag)

            self.session.commit()
            self.data_changed()
            return True
        except NoResultFound:
            raise DBusException('Tag does not exist')

    @dbus.service.method(
        "com.everpad.Provider", in_signature=btype.Tag.signature,
        out_signature=btype.Tag.signature,
    )
    def update_tag(self, tag_struct):
        """Update tag"""
        try:
            tag_btype = btype.Tag << tag_struct
            tag = self.session.query(models.Tag).filter(
                (models.Tag.id == tag_btype.id)
                & (models.Tag.action != const.ACTION_DELETE)
            ).one()

            if self.session.query(models.Tag).filter(
                (models.Tag.id != tag_btype.id)
                & (models.Tag.name == tag_btype.name)
            ).count():
                raise DBusException(
                    'Tag with this name already exist',
                )

            tag.action = const.ACTION_CHANGE
            tag_btype.give_to_obj(tag)
            self.session.commit()
            self.data_changed()

            return btype.Tag >> tag
        except NoResultFound:
            raise DBusException('Tag does not exist')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature=btype.Note.signature,
        out_signature=btype.Note.signature,
    )
    def create_note(self, note_struct):
        """Create new note"""
        note = models.Note(
            action=const.ACTION_NOEXSIST,
        )
        note_btype = btype.Note << note_struct
        note_btype.id = None
        note_btype.give_to_obj(note)

        note.updated = int(time.time() * 1000)
        note.created = int(time.time() * 1000)

        self.session.add(note)
        self.session.commit()
        self.data_changed()

        return btype.Note >> note

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature=btype.Note.signature,
        out_signature=btype.Note.signature,
    )
    def update_note(self, note_struct):
        """Update note"""
        note_btype = btype.Note << note_struct

        try:
            note = self.session.query(models.Note).filter(
                (models.Note.id == note_btype.id)
                & (models.Note.action != const.ACTION_DELETE)
            ).one()
        except NoResultFound:
            raise DBusException('Note not found')

        note_btype.give_to_obj(note)

        if note.action == const.ACTION_NOEXSIST:
            note.action = const.ACTION_CREATE
        elif note.action != const.ACTION_CREATE:
            note.action = const.ACTION_CHANGE

        note.updated_local = int(time.time() * 1000)
        self.session.commit()
        self.data_changed()

        return btype.Note >> note

    @dbus.service.method(
        "com.everpad.Provider", in_signature='i',
        out_signature='a{}'.format(btype.Resource.signature),
    )
    def get_note_resources(self, note_id):
        """Get note resources"""
        resources = self.session.query(models.Resource).filter(
            (models.Resource.note_id == note_id)
            & (models.Resource.action != const.ACTION_DELETE)
        )

        return btype.Resource.list >> resources

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='ia{}'.format(btype.Resource.signature),
        out_signature='{}'.format(btype.Note.signature),
    )
    def update_note_resources(self, note_id, resources_struct):
        """Update note resources"""
        try:
            note = self.session.query(models.Note).filter(
                models.Note.id == note_id,
            ).one()
        except NoResultFound:
            raise DBusException('models.Note not found')

        self.session.query(models.Resource).filter(
            models.Resource.note_id == note.id,
        ).delete()

        for resource_btype in btype.Resource.list << resources_struct:
            resource = models.Resource(
                action=const.ACTION_CREATE,
                note_id=note.id,
            )
            resource_btype.give_to_obj(resource)
            resource.id = None
            self.session.add(resource)

        if note.action != const.ACTION_CREATE:
            note.action = const.ACTION_CHANGE

        self.session.commit()
        self.data_changed()
        return btype.Note >> note

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='b',
    )
    def delete_note(self, note_id):
        """Delete note"""
        try:
            note = self.session.query(models.Note).filter(
                models.Note.id == note_id,
            ).one()

            if note.action == const.ACTION_CONFLICT:
                # prevent circular dependency error
                note.conflict_parent_id = None
                note.conflict_parent = []
                self.session.commit()
                self.session.delete(note)
            else:
                note.action = const.ACTION_DELETE

            self.session.commit()
            self.data_changed()
            return True
        except NoResultFound:
            raise DBusException('models.Note not found')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='ss',
        out_signature=btype.Notebook.signature,
    )
    def create_notebook(self, name, stack):
        """Create new notebook"""
        if self.session.query(models.Note).filter(
            models.Notebook.name == name,
        ).count():
            raise DBusException(
                'models.Notebook with this name already exist',
            )

        notebook = models.Notebook(
            action=const.ACTION_CREATE,
            name=name, default=False, stack=stack,
        )
        self.session.add(notebook)
        self.session.commit()
        self.data_changed()
        return btype.Notebook >> notebook

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='s', out_signature='',
    )
    def authenticate(self, token):
        """Authenticate client with token"""
        self.qobject.remove_authenticate_signal.emit()
        self.qobject.authenticate_signal.emit(token)
        if self.app.sync_thread.status != const.STATUS_SYNC:
            self.app.sync_thread.force_sync()
        self.data_changed()

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='',
    )
    def remove_authentication(self):
        """Remove authentication"""
        self.qobject.remove_authenticate_signal.emit()
        self.data_changed()

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='b',
    )
    def is_authenticated(self):
        """Check is client authenticated"""
        return bool(get_auth_token())

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='a%s' % btype.Place.signature,
    )
    def list_places(self):
        """List places"""
        places = self.session.query(models.Place).all()
        return btype.Place.list >> places

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='',
    )
    def share_note(self, note_id):
        """Share note"""
        try:
            note = self.session.query(models.Note).filter(
                (models.Note.id == note_id)
                & (models.Note.action != const.ACTION_DELETE)
            ).one()
            note.share_status = const.SHARE_NEED_SHARE
            self.session.commit()
            self.sync()
        except NoResultFound:
            raise DBusException('models.Note not found')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature=''
    )
    def stop_sharing_note(self, note_id):
        """Stop sharing note"""
        try:
            note = self.session.query(models.Note).filter(
                (models.Note.id == note_id)
                & (models.Note.action != const.ACTION_DELETE)
            ).one()
            note.share_status = const.SHARE_NEED_STOP
            note.share_url = ''
            self.session.commit()
            self.sync()
        except NoResultFound:
            raise DBusException('models.Note not found')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='i',
    )
    def get_status(self):
        """Get sync status"""
        return self.app.sync_thread.status

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='s',
    )
    def get_last_sync(self):
        """Get last sync date"""
        return self.app.sync_thread.last_sync.strftime('%H:%M')

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='',
    )
    def sync(self):
        """Preform sync"""
        if self.app.sync_thread.status != const.STATUS_SYNC:
            self.app.sync_thread.force_sync()
        return

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='i', out_signature='',
    )
    def set_sync_delay(self, delay):
        """Change sync delay"""
        self.app.settings.setValue('sync_delay', str(delay))
        self.app.sync_thread.update_timer()

    @dbus.service.method(
        "com.everpad.Provider",
        in_signature='', out_signature='i',
    )
    def get_sync_delay(self):
        """Get sync delay"""
        return int(self.app.settings.value('sync_delay') or 0)\
            or const.DEFAULT_SYNC_DELAY

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='b',
    )
    def is_first_synced(self):
        """Check is first sync performed"""
        return bool(self.session.query(models.Notebook).filter(
            (models.Notebook.action != const.ACTION_DELETE)
            & (models.Notebook.default == True)
        ).count())

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
        out_signature='i',
    )
    def get_api_version(self):
        """Get api version"""
        return const.API_VERSION

    @dbus.service.method(
        "com.everpad.Provider", in_signature='s',
        out_signature='s',
    )
    def get_settings_value(self, name):
        """Get settings value"""
        return self.app.settings.value(name, '')

    @dbus.service.method(
        "com.everpad.Provider", in_signature='ss',
        out_signature='',
    )
    def set_settings_value(self, name, value):
        """Set settings value"""
        self.app.settings.setValue(name, value)
        self.settings_changed(name, value)
        return

    @dbus.service.method(
        "com.everpad.Provider", in_signature='',
    )
    def kill(self):
        """Kill everpad"""
        self.qobject.terminate.emit()
        return

    @dbus.service.signal(
        'com.everpad.provider', signature='i',
    )
    def sync_state_changed(self, state):
        """Emit when sync state changed"""
        return

    @dbus.service.signal(
        'com.everpad.provider', signature='',
    )
    def data_changed(self):
        """Emit when data changed"""
        return

    @dbus.service.signal(
        'com.everpad.provider', signature='ss',
    )
    def settings_changed(self, name, value):
        """Emit when settings changed"""
        return
