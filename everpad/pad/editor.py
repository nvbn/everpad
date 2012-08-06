import sys
sys.path.append('../..')
from PySide.QtGui import QMainWindow
from PySide.QtCore import Slot
from everpad.interface.editor import Ui_Editor
from everpad.pad.tools import get_icon
from everpad.tools import provider
from everpad.basetypes import Note, Notebook
from BeautifulSoup import BeautifulSoup
import dbus


class Editor(QMainWindow):
    """Note editor"""

    def __init__(self, note, *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        self.closed = False
        self.ui = Ui_Editor()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.init_controls()
        self.load_note(note)

    def init_controls(self):
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSave_and_close.triggered.connect(self.save_and_close)
        self.ui.actionDelete.triggered.connect(self.delete)
        self.ui.actionClose.triggered.connect(self.close)
        for notebook_struct in provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            self.ui.notebook.addItem(notebook.name, userData=notebook.id)

    def load_note(self, note):
        self.note = note
        notebook_index = self.ui.notebook.findData(note.id)
        self.ui.notebook.setCurrentIndex(notebook_index)
        self.ui.title.setText(note.title)
        self.ui.content.setText(note.content)
        self.ui.tags.setText(', '.join(note.tags))

    def update_note(self):
        notebook_index = self.ui.notebook.currentIndex()
        self.note.notebook = self.ui.notebook.itemData(notebook_index)
        self.note.title = self.ui.title.text()
        soup = BeautifulSoup(self.ui.content.toHtml())
        self.note.content = ''.join(map(   # shit =)
            lambda tag: unicode(tag),
            soup.find('body').fetch(),
        ))
        self.note.tags = dbus.Array(map(
            lambda tag: tag.strip(),
            self.ui.tags.text().split(','),
        ), signature='s')

    def closeEvent(self, event):
        event.ignore()
        self.save()
        self.close()

    @Slot()
    def save(self):
        self.update_note()
        provider.update_note(self.note.struct)

    @Slot()
    def save_and_close(self):
        self.save()
        self.close()

    @Slot()
    def delete(self):
        self.update_note()
        provider.delete_note(self.note.id)
        self.close()

    @Slot()
    def close(self):
        self.hide()
        self.closed = True
