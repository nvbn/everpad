import sys
sys.path.append('../..')
from PySide.QtCore import Slot, QTranslator, QLocale, Signal
from PySide.QtGui import QApplication, QSystemTrayIcon, QMenu, QIcon
from everpad.basetypes import Note, Notebook, Tag, NONE_ID, NONE_VAL
from everpad.pad.tools import provider
from everpad.pad.editor import Editor
from functools import partial
import signal
import dbus
import argparse


class Indicator(QSystemTrayIcon):
    def __init__(self, *args, **kwargs):
        QSystemTrayIcon.__init__(self, *args, **kwargs)
        self.menu = QMenu()
        self.setContextMenu(self.menu)
        self.menu.aboutToShow.connect(self.update)
        self.opened_notes = {}

    @Slot()
    def update(self):
        self.menu.clear()
        for note_struct in provider.find_notes(
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
        self.menu.addAction(self.tr('Authorisation'), self.auth)
        self.menu.addSeparator()
        self.menu.addAction(self.tr('Exit'), self.exit)

    def open(self, note):
        old_note_window = self.opened_notes.get(note.id, None)
        if old_note_window and not getattr(old_note_window, 'closed', True):
            self.opened_notes[note.id].activateWindow()
        else:
            editor = Editor(note)
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
        p = provider.create_note(note_struct)
        note = Note.from_tuple(
            p,
        )
        self.open(note)

    @Slot()
    def auth(self):
        pass

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
        self.icon = QIcon.fromTheme('everpad', QIcon('../../everpad.png'))
        self.indicator = Indicator(self.icon)
        self.indicator.show()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', type=str, help='open note')
    parser.add_argument('--settings', action='store_true', help='open settings dialog')
    parser.add_argument('--create', action='store_true', help='create new note')
    args = parser.parse_args(sys.argv[1:])
    app = PadApp(sys.argv)
    app.exec_()


if __name__ == '__main__':
    main()
