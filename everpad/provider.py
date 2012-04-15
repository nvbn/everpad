from datetime import datetime
import dbus
import dbus.service
import dbus.mainloop.glib
from sqlite3 import OperationalError
import sys
import gconf
import signal
sys.path.insert(0, '..')
from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.type.ttypes import Note
import fcntl
from everpad.api import Api
from everpad.utils import SyncThread
from PySide.QtCore import QCoreApplication, QTimer, Slot, Signal, QThread
import sqlite3
import os
import keyring


class App(QCoreApplication):
    notes_receive = Signal(list)
    note_receive = Signal(Note)
    note_update = Signal(Note)
    note_remove = Signal(str)

    def __init__(self, *args, **kwargs):
        QCoreApplication.__init__(self, *args, **kwargs)
        self._api = None
        self.settings = gconf.client_get_default()
        self.db_path = os.path.expanduser('~/.evernote.db')
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        try:
            self.cursor.execute('''create table notes
                (owner text, guid text, title text, content text, updated text)
            ''')
        except OperationalError:
            pass
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.timer.setInterval(30 * 60 * 1000)
        self.timer.start()
        self.notes_receive.connect(self.notes_received)
        self.note_receive.connect(self.note_received)
        self.note_update.connect(self.note_updated)
        self.note_remove.connect(self.note_removed)
        self.sync_thread = SyncThread()
        self.sync_thread.start()
        self.sync()

    def get_auth_data(self):
        login = self.settings.get_string('/apps/everpad/login')
        return login, keyring.get_password('everpad', login)

    def get_api(self):
        self.user, self.password = self.get_auth_data()
        self.authenticated = True
        try:
            return Api(self.user, self.password)
        except EDAMUserException:
            self.authenticated = False
            return None

    @property
    def api(self):
        if not getattr(self, '_api', None) or\
            (self.user, self.password) != self.get_auth_data() or\
            datetime.now() > getattr(self._api, 'expire', datetime.min):
            self._api = self.get_api()
        return self._api

    def to_db(self, note, api):
        self.cursor.execute('''insert into notes
            values (?, ?, ?, ?, ?)
        ''', (
            api.username, note.guid,
            note.title.decode('utf8'),
            note.content.decode('utf8'),
            note.updated,
        ))

    @Slot(Note)
    def note_received(self, note):
        self.to_db(note, self.api)

    @Slot(list)
    def notes_received(self, notes):
        guids = []
        for note in notes:
            self.cursor.execute('select updated from notes where guid = ?', (note.guid,))
            try:
                fresh = list(self.cursor)[0][0] == note.updated
                if not fresh:
                    self.cursor.execute('delete from notes where guid = ?', (note.guid,))
            except IndexError:
                fresh = False
            if fresh:
                guids.append(note.guid)
            else:
                self.sync_thread.action_receive.emit((
                    self.api.get_note,
                    (note.guid,), {},
                    self.note_receive,
                ))
        if len(guids):
            self.cursor.execute(
                'delete from notes where guid not in (%s)' % ', '.join(
                    ['?'] * len(guids)
                ), guids,
            )

    @Slot()
    def sync(self):
        if self.api:
            self.sync_thread.action_receive.emit((
                self.api.get_notes,
                tuple(), {},
                self.notes_receive,
            ))

    @Slot(Note)
    def note_updated(self, note):
        self.cursor.execute('delete from notes where guid = ?', (note.guid,))
        self.to_db(note, self.api)

    def update_note(self, guid, title, content):
        note = self.api.get_note(guid)
        note.title = self.api.parse_title(title)
        note.content = self.api.parse_content(content)
        self.sync_thread.action_receive.emit((
            self.api.update_note,
            (note,), {},
            self.note_update,
        ))

    def create_note(self, title, content):
        note = self.api.create_note(title, content)
        note = self.api.get_note(note.guid)
        self.to_db(note, self.api)
        return note.guid

    @Slot(Note)
    def note_removed(self, guid):
        self.cursor.execute('delete from notes where guid = ?', (guid,))
        self.conn.commit()

    def remove_note(self, guid):
        self.sync_thread.action_receive.emit((
            self.api.remove_note, (guid,),
            {}, self.note_remove,
        ))

    def get_notes(self, words, count):
        if not self.api:
            return []
        query = 'select * from notes where owner = ? %(where)s %(limit)s'
        params = {'where': '', 'limit': ''}
        args = [self.api.username]
        if words:
            params['where'] = 'and title like ? or content like ?'
            args += ['%%%s%%' % words] * 2
        if count:
            params['limit'] = 'LIMIT ?'
            args.append(count)
        self.cursor.execute(query % params, args)
        return list(self.cursor)

    def get_note(self, guid):
        self.cursor.execute('select * from notes where guid = ? limit 1', (guid,))
        return list(self.cursor)[0]


class EverpadService(dbus.service.Object):
    def __init__(self, app, *args, **kwargs):
        self.app = app
        dbus.service.Object.__init__(self, *args, **kwargs)

    @dbus.service.method("com.everpad.Provider", in_signature='s', out_signature='(sssss)')
    def get_note(self, guid):
        return dbus.Struct(self.app.get_note(guid))

    @dbus.service.method("com.everpad.Provider", in_signature='si', out_signature='a(sssss)')
    def get_notes(self, words, count):
        return dbus.Array(self.app.get_notes(words, count), '(sssss)')

    @dbus.service.method("com.everpad.Provider", in_signature='sss', out_signature='')
    def update_note(self, guid, title, content):
        self.app.update_note(guid, title, content)

    @dbus.service.method("com.everpad.Provider", in_signature='ss', out_signature='s')
    def create_note(self, title, content):
        return self.app.create_note(title, content)

    @dbus.service.method("com.everpad.Provider", in_signature='s', out_signature='')
    def remove_note(self, guid):
        self.app.remove_note(guid)

    @dbus.service.method("com.everpad.Provider", in_signature='', out_signature='b')
    def authenticated(self):
        return self.app.authenticated


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    fp = open('/tmp/everpad-provider.lock', 'w')
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    app = App(sys.argv)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    app.bus = dbus.service.BusName("com.everpad.Provider", session_bus)
    app.service = EverpadService(app, session_bus, '/EverpadProvider')
    app.exec_()

if __name__ == '__main__':
    main()
