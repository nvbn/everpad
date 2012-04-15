import argparse
import sys
import fcntl
import signal

sys.path.insert(0, '..')
from functools import partial
from PySide.QtCore import Slot, QTranslator, QLocale, Signal
from PySide.QtGui import QApplication, QSystemTrayIcon, QIcon, QMenu, QMainWindow, QDialog, QMessageBox
from BeautifulSoup import BeautifulSoup
from everpad.interface.auth import Ui_Dialog as AuthDialogUi
from everpad.interface.note import Ui_MainWindow as NoteUi
from everpad.utils import SyncThread
import dbus
import dbus.service
import dbus.mainloop.glib
import gconf
import keyring


class AuthDialog(QDialog):
    """Authorisation dialog"""

    def __init__(self, app):
        """Init dialog and setup ui

        Keyword Arguments:
        app - QApplication

        Returns: None
        """
        QDialog.__init__(self)
        self.ui = AuthDialogUi()
        self.ui.setupUi(self)
        self.setWindowIcon(app.icon)
        self.setWindowTitle('everpad')
        self.app = app

    def accept(self, *args, **kwargs):
        """Save settings"""
        login = self.ui.login.text()
        self.app.settings.set_string('/apps/everpad/login', login)
        keyring.set_password('everpad', login, self.ui.password.text())
        self.hide()

    def reject(self, *args, **kwargs):
        """Hide settings window"""
        self.hide()

    def closeEvent(self, event):
        """Only hide, not close app"""
        self.hide()
        event.ignore()


class NoteWindow(QMainWindow):
    """Note window"""
    note_remove = Signal()
    note_create = Signal(str)

    def __init__(self, app, note, create, *args, **kwargs):
        """Init window, connect signals with slots

        Keyword Arguments:
        app -- QApplication
        note -- Note

        Returns: None
        """
        QMainWindow.__init__(self, *args, **kwargs)
        self._action_threads = []
        self.ui = NoteUi()
        self.ui.setupUi(self)
        self.setWindowIcon(app.icon)
        self.create = create
        if create:
            title = self.tr('Note title')
            text = self.tr('<div>Note text</div>')
            self.guid = None
        else:
            self.guid, title, text = note[1:4]
        prepared = '<h2 id="note-title">%s</h2>%s' % (title, text)
        self.ui.text.setText(prepared)
        self.text = self.ui.text
        self.setWindowTitle(title)
        self.note = note
        self.app = app
        self.save_on_close = True
        self.ui.toolBar.addAction(QIcon.fromTheme('document-save'), self.tr('Save'), Slot()(self.save))
        self.ui.toolBar.addAction(QIcon.fromTheme('cancel'), self.tr('Close without saving'), self.close_wo_save)
        self.delete = self.ui.toolBar.addAction(QIcon.fromTheme('edit-delete'), self.tr('Remove note'), self.remove_note)
        if self.create:
            self.delete.setEnabled(False)
        self.ui.toolBar.addSeparator()
        cut = self.ui.toolBar.addAction(QIcon.fromTheme('edit-cut'), self.tr('Cut'), self.text.cut)
        self.text.copyAvailable.connect(cut.setEnabled)
        cut.setEnabled(False)
        copy = self.ui.toolBar.addAction(QIcon.fromTheme('edit-copy'), self.tr('Copy'), self.text.copy)
        self.text.copyAvailable.connect(copy.setEnabled)
        copy.setEnabled(False)
        self.ui.toolBar.addAction(QIcon.fromTheme('edit-paste'), self.tr('Paste'), self.text.paste)
        self.text.copyAvailable.connect(self.ui.actionCopy.setEnabled)
        self.ui.actionCopy.setEnabled(False)
        self.text.copyAvailable.connect(self.ui.actionCut.setEnabled)
        self.ui.actionCut.setEnabled(False)
        self.ui.actionSave.triggered.connect(Slot()(self.save))
        self.ui.actionClose_and_save.triggered.connect(self.close)
        self.ui.actionClose_without_saving.triggered.connect(self.close_wo_save)
        self.ui.actionRemove.triggered.connect(self.remove_note)
        self.note_create.connect(self.note_created)
        self.closed = False

    def closeEvent(self, event):
        """Close w/wo saving"""
        event.ignore()
        self.hide()
        if self.save_on_close:
            self.save()
        self.app.indicator.get_notes()
        self.closed = True

    @Slot()
    def close_wo_save(self):
        """Close without saving note"""
        self.save_on_close = False
        self.close()

    def get_data(self):
        title = self.text.toPlainText().split('\n')[0]
        html = self.text.toHtml()
        soup = BeautifulSoup(html)
        body = soup.find('body')
        html = reduce(lambda txt, cur: txt + unicode(cur), body.contents[2:], u'')
        return title, html

    @Slot(str)
    def note_created(self, guid):
        self.guid = guid
        self.create = False
        self.delete.setEnabled(True)

    def save(self):
        """Save note"""
        title, html = self.get_data()
        if self.create:
            self.app.sync_thread.action_receive.emit((
                self.app.provider.create_note,
                (title, html), {},
                self.note_create,
            ))
            self.app.send_notify(
                self.tr('Note created'),
                self.tr('Note "%s" created') % title,
            )
        else:
            self.app.sync_thread.action_receive.emit((
                self.app.provider.update_note,
                (self.guid, title, html),
            ))
            self.app.send_notify(
                self.tr('Note saved'),
                self.tr('Note "%s" saved') % title,
            )

    @Slot()
    def remove_note(self):
        """Remove note in new thread"""
        msgBox = QMessageBox(
            QMessageBox.Critical,
            self.tr("You try to delete a note"),
            self.tr("Are you sure want to delete a note?"),
            QMessageBox.Yes | QMessageBox.No
        )
        ret = msgBox.exec_()
        if ret == QMessageBox.Yes:
            self.app.sync_thread.action_receive.emit((
                self.app.provider.remove_note,
                (self.note[1],),
            ))
            self.app.send_notify(
                self.tr('Note removed'),
                self.tr('Note "%s" removed') % self.note[2],
            )
            self.close_wo_save()


class App(QApplication):
    """Main class"""

    def __init__(self, *args, **kwargs):
        """Init app"""
        QApplication.__init__(self, *args, **kwargs)
        self.sync_thread = SyncThread()
        self.sync_thread.start()
        self.translator = QTranslator()
        if not self.translator.load('i18n/%s' % QLocale.system().name()):
            self.translator.load('/usr/share/everpad/lang/%s' % QLocale.system().name())
        self.provider_obj = dbus.SessionBus().get_object("com.everpad.Provider", '/EverpadProvider')
        self.provider = dbus.Interface(self.provider_obj, "com.everpad.Provider")
        self.installTranslator(self.translator)
        self.icon = QIcon.fromTheme('everpad', QIcon('../everpad.png'))
        indicator = Indicator(self, self.icon)
        indicator.show()
        self.opened = {}
        self.setApplicationName('everpad')
        self.settings = gconf.client_get_default()

    @property
    def authenticated(self):
        return self.provider.authenticated()

    def send_notify(self, title, text, icon=QSystemTrayIcon.Information):
        """Send osd"""
        self.indicator.showMessage(
            title, text, icon,
        )

    @Slot()
    def end(self):
        """Exit app"""
        self.exit()


class Indicator(QSystemTrayIcon):
    """Indicator applet class"""
    notes_get = Signal(list)

    def __init__(self, app, *args, **kwargs):
        """Init indicator

        Keyword Arguments:
        app -- QApplication

        Returns: None
        """
        QSystemTrayIcon.__init__(self, *args, **kwargs)
        self._action_threads = []
        self._cached_notes = {}
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.app = app
        app.indicator = self
        self.menu.aboutToShow.connect(self.update)
        self.auth_dialog = AuthDialog(self.app)
        self._notes = []
        self.notes_get.connect(self.notes_getted)
        self.get_notes()

    @Slot(list)
    def notes_getted(self, notes):
        self._notes = notes

    def get_notes(self):
        self.app.sync_thread.action_receive.emit((
            self.app.provider.get_notes,
            ('', 10), {}, self.notes_get,
        ))

    @Slot()
    def update(self):
        """Set notes to menu"""
        self.menu.clear()
        self._open_slots = []
        if self.app.authenticated:
            for note in self._notes:
                slot = Slot()(partial(self.show_note, note[1]))
                self._open_slots.append(slot)
                self.menu.addAction(
                    note[2][:40],
                    slot,
                )
            self.menu.addSeparator()
            self.menu.addAction(
                self.tr('New note'),
                self.new_note,
            )
            self.menu.addAction(
                self.tr('Auth settings'),
                self.auth_settings,
            )
        else:
            self.menu.addAction(
                self.tr('Please authorise'),
                self.auth_settings,
            )
        self.menu.addAction(self.tr('Exit'), self.app.end)
        self.get_notes()


    @Slot()
    def new_note(self):
        """Create new note"""
        self.show_note(None, True)

    @Slot()
    def auth_settings(self):
        """Show auth settings dialog"""
        self.auth_dialog.show()

    def show_note(self, id, create=False):
        """Show note"""
        if create:
            note = None
        else:
            note = self.app.provider.get_note(id)
        prev = self.app.opened.get(id, None)
        if not prev or getattr(prev, 'closed', False):
            self.app.opened[id] = NoteWindow(self.app, note, create)
            self.app.opened[id].show()


class EverpadService(dbus.service.Object):
    def __init__(self, app, *args, **kwargs):
        self.app = app
        dbus.service.Object.__init__(self, *args, **kwargs)

    @dbus.service.method("com.everpad.App", in_signature='s', out_signature='')
    def open_note(self, id):
        self.app.indicator.show_note(id)

    @dbus.service.method("com.everpad.App", in_signature='', out_signature='')
    def open_settings(self):
        self.app.indicator.auth_settings()

    @dbus.service.method("com.everpad.App", in_signature='', out_signature='')
    def create_note(self):
        self.app.indicator.new_note()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', type=str, help='open note')
    parser.add_argument('--settings', action='store_true', help='open settings dialog')
    parser.add_argument('--create', action='store_true', help='create new note')
    args = parser.parse_args(sys.argv[1:])
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    fp = open('/tmp/everpad.lock', 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        app = App(sys.argv)
        if args.open:
            app.indicator.show_note(args.open)
        elif args.settings:
            app.indicator.auth_settings()
        elif args.create:
            app.indicator.new_note()
        app.bus = dbus.service.BusName("com.everpad.App", session_bus)
        app.service = EverpadService(app, session_bus, '/EverpadService')
        app.exec_()
    except IOError:
        app = session_bus.get_object("com.everpad.App", '/EverpadService')
        interface = dbus.Interface(app, "com.everpad.App")
        if args.open:
            interface.open_note(args.open)
        elif args.settings:
            interface.open_settings()
        elif args.create:
            interface.create_note()
        sys.exit(0)

if __name__ == '__main__':
    main()
