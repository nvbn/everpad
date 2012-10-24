import sys
sys.path.insert(0, '../..')
from PySide.QtCore import Slot, QTranslator, QLocale, Signal, QSettings
from PySide.QtGui import QApplication, QSystemTrayIcon, QMenu, QIcon
from everpad.basetypes import Note, Notebook, Tag, NONE_ID, NONE_VAL
from everpad.tools import get_provider, get_pad, get_auth_token
from everpad.pad.editor import Editor
from everpad.pad.management import Management
from everpad.pad.list import List
from everpad.const import STATUS_SYNC, SYNC_STATES, SYNC_STATE_START, SYNC_STATE_FINISH
from functools import partial
import signal
import dbus
import dbus.service
import dbus.mainloop.glib
import argparse
import fcntl
import os
import getpass


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
        if get_auth_token():
            notes = self.app.provider.find_notes(
                '', dbus.Array([], signature='i'),
                dbus.Array([], signature='i'), 0,
                20, Note.ORDER_UPDATED_DESC,
            )
            if len(notes) or self.app.provider.is_first_synced():
                self.menu.addAction(self.tr('All Notes'), self.show_all_notes)
                self.menu.addSeparator()
                for note_struct in notes:
                    note = Note.from_tuple(note_struct)
                    title = note.title[:40].replace('&', '&&')
                    self.menu.addAction(title, Slot()(
                        partial(self.open, note=note)
                    ))
                self.menu.addSeparator()
                self.menu.addAction(self.tr('Create Note'), self.create)
                first_sync = False
            else:
                first_sync = True
            if self.app.provider.get_status() == STATUS_SYNC:
                action = self.menu.addAction(
                    self.tr('Wait, first sync in progress') if first_sync
                    else self.tr('Sync in progress')
                )
                action.setEnabled(False)
            else:
                if first_sync:
                    label = self.tr('Please perform first sync')
                else:
                    label = self.tr('Last sync: %s') % self.app.provider.get_last_sync()
                self.menu.addAction(label, Slot()(self.app.provider.sync))
        self.menu.addAction(self.tr('Settings and Management'), self.show_management)
        self.menu.addSeparator()
        self.menu.addAction(self.tr('Exit'), self.exit)

    def open(self, note, search_term=''):
        old_note_window = self.opened_notes.get(note.id, None)
        if old_note_window and not getattr(old_note_window, 'closed', True):
            editor = self.opened_notes[note.id]
            editor.activateWindow()
        else:
            editor = Editor(self.app, note)
            editor.show()
            self.opened_notes[note.id] = editor
        if search_term:
            editor.findbar.set_search_term(search_term)
            editor.findbar.show()
        return editor

    @Slot()
    def create(self, attach=None, notebook_id=NONE_ID):
        note_struct = Note(  # maybe replace NONE's to somthing better
            id=NONE_ID,
            title=self.tr('New note'),
            content=self.tr("New note content"),
            tags=dbus.Array([], signature='i'),
            notebook=notebook_id,
            created=NONE_VAL,
            updated=NONE_VAL,
            place='',
        ).struct
        note = Note.from_tuple(
            self.app.provider.create_note(note_struct),
        )
        editor = self.open(note)
        if attach:
            editor.resource_edit.add_attach(attach)

    @Slot()
    def show_all_notes(self):
        if not hasattr(self, 'list') or getattr(self.list, 'closed', True):
            self.list = List(self.app)
            self.list.show()
        else:
            self.list.activateWindow()

    @Slot()
    def show_management(self):
        if not hasattr(self, 'management') or getattr(self.management, 'closed', True):
            self.management = Management(self.app)
            self.management.show()
        else:
            self.management.activateWindow()

    @Slot()
    def exit(self):
        sys.exit(0)


class PadApp(QApplication):
    def __init__(self, *args, **kwargs):
        QApplication.__init__(self, *args, **kwargs)
        self.settings = QSettings('everpad', 'everpad-pad')
        self.translator = QTranslator()
        if not self.translator.load('../../i18n/%s' % QLocale.system().name()):
            self.translator.load('/usr/share/everpad/i18n/%s' % QLocale.system().name())
        self.installTranslator(self.translator)
        self.indicator = Indicator(self)
        self.update_icon()
        self.indicator.show()

    def update_icon(self):
        if int(self.settings.value('black-icon', 0)):
            self.icon = QIcon.fromTheme('everpad-black', QIcon('../../data/everpad-black.png'))
        else:
            self.icon = QIcon.fromTheme('everpad-mono', QIcon('../../data/everpad-mono.png'))
        self.indicator.setIcon(self.icon)

    def send_notify(self, text):
        self.indicator.showMessage('Everpad', text,
            QSystemTrayIcon.Information)

    def on_sync_state_changed(self, state):
        self.launcher.update({
            'progress': float(state + 1) / len(SYNC_STATES),
            'progress-visible': state not in (SYNC_STATE_START, SYNC_STATE_FINISH),
        })


class EverpadService(dbus.service.Object):
    def __init__(self, app, *args, **kwargs):
        self.app = app
        dbus.service.Object.__init__(self, *args, **kwargs)

    @dbus.service.method("com.everpad.App", in_signature='i', out_signature='')
    def open(self, id):
        self.open_with_search_term(id, '')

    @dbus.service.method("com.everpad.App", in_signature='is', out_signature='')
    def open_with_search_term(self, id, search_term):
        note = Note.from_tuple(self.app.provider.get_note(id))
        self.app.indicator.open(note, search_term)

    @dbus.service.method("com.everpad.App", in_signature='', out_signature='')
    def create(self):
        self.app.indicator.create()

    @dbus.service.method("com.everpad.App", in_signature='s', out_signature='')
    def create_wit_attach(self, name):
        self.app.indicator.create(name)

    @dbus.service.method("com.everpad.App", in_signature='', out_signature='')
    def settings(self):
        self.app.indicator.show_management()


class UnityLauncher(dbus.service.Object):
    def __init__(self, app_uri, *args, **kwargs):
        self.app_uri = app_uri
        self.data = {}
        dbus.service.Object.__init__(self, *args, **kwargs)

    def update(self, data):
        self.data = data
        self.Update(self.app_uri, data)

    @dbus.service.signal(
        dbus_interface='com.canonical.Unity.LauncherEntry',
        signature=("sa{sv}")
    )
    def Update(self, app_uri, properties):
        return

    @dbus.service.method(
        dbus_interface='com.canonical.Unity.LauncherEntry',
        in_signature="", out_signature="sa{sv}",
    )
    def Query(self):
        return self.app_uri, self.data


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument('attach', type=str, nargs='?', help='attach file to new note')
    parser.add_argument('--open', type=int, help='open note')
    parser.add_argument('--create', action='store_true', help='create new note')
    parser.add_argument('--settings', action='store_true', help='settings and management')
    args = parser.parse_args(sys.argv[1:])
    fp = open('/tmp/everpad-%s.lock' % getpass.getuser(), 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        app = PadApp(sys.argv)
        app.setApplicationName('everpad')
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        session_bus = dbus.SessionBus()
        app.provider = get_provider(session_bus)
        app.launcher = UnityLauncher('application://everpad.desktop', session_bus, '/')
        app.provider.connect_to_signal(
            'sync_state_changed',
            app.on_sync_state_changed,
            dbus_interface="com.everpad.provider",
        )
        bus = dbus.service.BusName("com.everpad.App", session_bus)
        service = EverpadService(app, session_bus, '/EverpadService')
        if args.open:
            app.indicator.open(args.open)
        if args.create:
            app.indicator.create()
        if args.settings:
            app.indicator.show_management()
        if args.attach:
            app.indicator.create(args.attach)
        app.exec_()
    except IOError:
        pad = get_pad()
        if args.open:
            pad.open(args.open)
        if args.create:
            pad.create()
        if args.settings:
            pad.settings()
        if args.attach:
            pad.create_wit_attach(args.attach)
        sys.exit(0)

if __name__ == '__main__':
    main()
