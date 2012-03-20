import dbus
import dbus.service
import dbus.mainloop.glib
from sqlite3 import OperationalError
import sys
import gconf
sys.path.insert(0, '..')
from evernote.edam.error.ttypes import EDAMUserException
import fcntl
from everpad.api import Api
from PySide.QtCore import QCoreApplication, QThread, QTimer, Slot
import sqlite3
import os


class ActionThread(QThread):
    """Thread for custom actions"""

    def __init__(self, action, *args, **kwargs):
        """Init thread with action

        Keyword Arguments:
        action -- callable

        Returns: None
        """
        self.action = action
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        """Run thread with action"""
        self.action()
        self.exit()


class App(QCoreApplication):
    def __init__(self, *args, **kwargs):
        QCoreApplication.__init__(self, *args, **kwargs)
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
        self.sync()

    def api(self):
        user = self.settings.get_string('/apps/everpad/login')
        password = self.settings.get_string('/apps/everpad/password')
        self.authenticated = True
        try:
            return Api(user, password)
        except EDAMUserException:
            self.authenticated = False
            return False

    def to_db(self, note, api):
        self.cursor.execute('''insert into notes
            values (?, ?, ?, ?, ?)
        ''', (
            api.username, note.guid,
            note.title.decode('utf8'),
            note.content.decode('utf8'),
            note.updated,
        ))

    @Slot()
    def sync(self):
        api = self.api()
        if api:
            for note in api.get_notes():
                self.cursor.execute('select updated from notes where guid = ?', (note.guid,))
                try:
                    fresh = list(self.cursor)[0][0] == note.updated
                    if not fresh:
                        self.cursor.execute('delete from notes where guid = ?', (note.guid,))
                except IndexError:
                    fresh = False
                if not fresh:
                    self.to_db(api.get_note(note.guid), api)
            self.conn.commit()

    def update_note(self, guid, title, content):
        api = self.api()
        note = api.get_note(guid)
        note.title = api.parse_title(title)
        note.content = api.parse_content(content)
        api.update_note(note)
        self.cursor.execute('delete from notes where guid = ?', (guid,))
        self.to_db(note, api)

    def create_note(self, title, content):
        api = self.api()
        note = api.create_note(title, content)
        note.content = content
        self.to_db(note, api)
        return note.guid

    def remove_note(self, guid):
        api = self.api()
        api.remove_note(guid)
        self.cursor.execute('delete from notes where guid = ?', (guid,))
        self.conn.commit()

    def get_notes(self, words, count):
        api = self.api()
        if not api:
            return []
        query = 'select * from notes where owner = ? %(where)s %(limit)s'
        params = {'where': '', 'limit': ''}
        args = [api.username]
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
