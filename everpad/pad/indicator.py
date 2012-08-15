import sys
sys.path.insert(0, '../..')
from PySide.QtCore import Slot, QTranslator, QLocale, Signal
from PySide.QtGui import QApplication, QSystemTrayIcon, QMenu, QIcon
from everpad.basetypes import Note, Notebook, Tag, NONE_ID, NONE_VAL
from everpad.tools import get_provider, get_pad
from everpad.pad.editor import Editor
from everpad.const import CONSUMER_KEY, CONSUMER_SECRET, HOST, STATUS_SYNC
from functools import partial
import everpad.monkey
import signal
import dbus
import dbus.service
import dbus.mainloop.glib
import argparse
import oauth2 as oauth
import subprocess
import webbrowser
import urllib
import urlparse
import keyring
import fcntl
import os


class Indicator(QSystemTrayIcon):
    def __init__(self, app, *args, **kwargs):
        QSystemTrayIcon.__init__(self, *args, **kwargs)
        self.app = app
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.menu.aboutToShow.connect(self.update)
        self.opened_notes = {}

    @Slot()
    def update(self):
        self.menu.clear()
        if keyring.get_password('everpad', 'oauth_token'):
            for note_struct in self.app.provider.find_notes(
                '', dbus.Array([], signature='i'),
                dbus.Array([], signature='i'), 20,
                Note.ORDER_UPDATED_DESC,
            ):
                note = Note.from_tuple(note_struct)
                self.menu.addAction(note.title[:40], Slot()(
                    partial(self.open, note=note)
                ))
            self.menu.addSeparator()
            self.menu.addAction(self.tr('Create Note'), self.create)
            if self.app.provider.get_status() == STATUS_SYNC:
                action = self.menu.addAction(self.tr('Sync in progress'))
                action.setEnabled(False)
            else:
                self.menu.addAction(self.tr('Last sync: %s') % 
                    self.app.provider.get_last_sync(),
                Slot()(self.app.provider.sync))
        else:
            self.menu.addAction(self.tr('Authorisation'), self.auth)
        self.menu.addSeparator()
        self.menu.addAction(self.tr('Exit'), self.exit)

    def open(self, note):
        old_note_window = self.opened_notes.get(note.id, None)
        if old_note_window and not getattr(old_note_window, 'closed', True):
            self.opened_notes[note.id].activateWindow()
        else:
            editor = Editor(self.app, note)
            editor.show()
            self.opened_notes[note.id] = editor

    @Slot()
    def create(self):
        note_struct = Note(  # maybe replace NONE's to somthing better
            id=NONE_ID,
            title=self.tr('New note'),
            content=self.tr("New note content"),
            tags=dbus.Array([], signature='i'),
            notebook=NONE_ID,
            created=NONE_VAL,
            updated=NONE_VAL,
        ).struct
        note = Note.from_tuple(
            self.app.provider.create_note(note_struct),
        )
        self.open(note)

    @Slot()
    def auth(self):
        consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
        client = oauth.Client(consumer)
        resp, content = client.request(
            'https://%s/oauth?oauth_callback=' % HOST + urllib.quote('http://localhost:15216/'), 
        'GET')
        data = dict(urlparse.parse_qsl(content))
        url = 'https://%s/OAuth.action?oauth_token=' % HOST + urllib.quote(data['oauth_token'])
        webbrowser.open(url)
        os.system('killall everpad-web-auth')
        try:
            subprocess.Popen([
                'everpad-web-auth', '--token', data['oauth_token'],
                '--secret', data['oauth_token_secret'],
            ])
        except OSError:
            subprocess.Popen([
                'python', '../auth.py', '--token',
                data['oauth_token'], '--secret',
                data['oauth_token_secret'],
            ])

    @Slot()
    def exit(self):
        sys.exit(0)


class PadApp(QApplication):
    def __init__(self, *args, **kwargs):
        QApplication.__init__(self, *args, **kwargs)
        self.translator = QTranslator()
        if not self.translator.load('i18n/%s' % QLocale.system().name()):
            self.translator.load('/usr/share/everpad/lang/%s' % QLocale.system().name())
        self.installTranslator(self.translator)
        self.icon = QIcon.fromTheme('everpad-mono', QIcon('../../everpad-mono.png'))
        self.indicator = Indicator(self, self.icon)
        self.indicator.show()

    def send_notify(self, text):
        self.indicator.showMessage('Everpad', text,
            QSystemTrayIcon.Information)


class EverpadService(dbus.service.Object):
    def __init__(self, app, *args, **kwargs):
        self.app = app
        dbus.service.Object.__init__(self, *args, **kwargs)

    @dbus.service.method("com.everpad.App", in_signature='i', out_signature='')
    def open(self, id):
        note = Note.from_tuple(self.app.provider.get_note(id))
        self.app.indicator.open(note)

    @dbus.service.method("com.everpad.App", in_signature='', out_signature='')
    def create(self):
        self.app.indicator.create()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', type=int, help='open note')
    parser.add_argument('--create', action='store_true', help='create new note')
    args = parser.parse_args(sys.argv[1:])
    fp = open('/tmp/everpad.lock', 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        app = PadApp(sys.argv)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        session_bus = dbus.SessionBus()
        app.provider = get_provider(session_bus) 
        bus = dbus.service.BusName("com.everpad.App", session_bus)
        service = EverpadService(app, session_bus, '/EverpadService')
        if args.open:
            app.open(args.open)
        if args.create:
            app.create()
        app.exec_()
    except IOError:
        pad = get_pad()
        if args.open:
            pad.open(args.open)
        if args.create:
            pad.create()
        sys.exit(0)

if __name__ == '__main__':
    main()
