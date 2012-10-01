# -*- coding:utf-8 -*-
import sys

sys.path.append('../..')
from PySide.QtGui import (
    QDialog, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction, QWidget,
    QListWidgetItem, QMenu, QInputDialog,
    QStandardItemModel, QStandardItem
    )
from PySide.QtCore import Slot
from everpad.interface.list import Ui_List
from everpad.pad.tools import get_icon
from everpad.basetypes import Notebook, Note

class List(QDialog):
    """All Notes dialog"""

    def __init__(self, app, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.app = app
        self.closed = False
        self.ui = Ui_List()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())

        self.notebooksModel = QStandardItemModel()
        self.ui.notebooksList.setModel(self.notebooksModel)
        self.ui.notebooksList.clicked.connect(self.notebook_selected)

        self.notesModel = QStandardItemModel()
        self.ui.notesList.setModel(self.notesModel)
        self.ui.notesList.doubleClicked.connect(self.note_dblclicked)

    def showEvent(self, *args, **kwargs):
        QDialog.showEvent(self, *args, **kwargs)

        self.notebooksModel.clear()
        self.notebooksModel.appendRow(QStandardItem(QIcon.fromTheme('user-home'), 'All Notes'))

        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            count = self.app.provider.get_notebook_notes_count(notebook.id)
            self.notebooksModel.appendRow(QNotebookItem(notebook, count))

        self.ui.notebooksList.setCurrentIndex(self.notebooksModel.index(0, 0))
        self.notebook_selected(self.notebooksModel.index(0, 0))

    def closeEvent(self, event):
        event.ignore()
        self.closed = True
        self.hide()

    @Slot()
    def notebook_selected(self, index):
        self.notesModel.clear()

        item = self.notebooksModel.itemFromIndex(index)
        notebook_id = item.notebook.id if index.row() else 0
        notes = self.app.provider.list_notebook_notes(notebook_id, sys.maxint, Note.ORDER_TITLE)
        for note_struct in notes:
            note = Note.from_tuple(note_struct)
            self.notesModel.appendRow(QNoteItem(note))

    @Slot()
    def note_dblclicked(self, index):
        item = self.notesModel.itemFromIndex(index)
        self.app.indicator.open(item.note)


class QNotebookItem(QStandardItem):
    def __init__(self, notebook, count):
        super(QNotebookItem, self).__init__(QIcon.fromTheme('folder'), '%s (%d)' % (notebook.name, count))
        self.notebook = notebook


class QNoteItem(QStandardItem):
    def __init__(self, note):
        super(QNoteItem, self).__init__(QIcon.fromTheme('x-office-document'), note.title)
        self.note = note
