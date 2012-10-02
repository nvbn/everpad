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
from everpad.basetypes import Notebook, Note, NONE_ID

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

        self.ui.newNotebookBtn.setIcon(QIcon.fromTheme('folder-new'))
        self.ui.newNotebookBtn.clicked.connect(self.new_notebook)

        self.ui.newNoteBtn.setIcon(QIcon.fromTheme('document-new'))
        self.ui.newNoteBtn.clicked.connect(self.new_note)

    def showEvent(self, *args, **kwargs):
        QDialog.showEvent(self, *args, **kwargs)
        self._reload_notebooks_list()

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

    @Slot()
    def new_notebook(self):
        name, status = self._notebook_new_name(self.tr('Create new notebook'))
        if status:
            notebook_struct = self.app.provider.create_notebook(name)
            notebook = Notebook.from_tuple(notebook_struct)

            self.app.send_notify(self.tr('Notebook "%s" created!') % notebook.name)
            self._reload_notebooks_list(notebook.id)

    @Slot()
    def new_note(self):
        index = self.ui.notebooksList.currentIndex()
        notebook_id = NONE_ID
        if index.row():
            item = self.notebooksModel.itemFromIndex(index)
            notebook_id = item.notebook.id

        self.app.indicator.create(notebook_id=notebook_id)

    def _reload_notebooks_list(self, select_notebook_id=None):
        self.notebooksModel.clear()
        self.notebooksModel.appendRow(QStandardItem(QIcon.fromTheme('user-home'), 'All Notes'))

        index_row = row = 0
        for notebook_struct in self.app.provider.list_notebooks():
            row += 1
            notebook = Notebook.from_tuple(notebook_struct)
            count = self.app.provider.get_notebook_notes_count(notebook.id)
            self.notebooksModel.appendRow(QNotebookItem(notebook, count))

            if select_notebook_id and notebook.id == select_notebook_id:
                index_row = row

        self.ui.notebooksList.setCurrentIndex(self.notebooksModel.index(index_row, 0))
        self.notebook_selected(self.notebooksModel.index(index_row, 0))

    def _notebook_new_name(self, title, exclude=''):
        names = map(lambda nb: Notebook.from_tuple(nb).name, self.app.provider.list_notebooks())
        try:
            names.remove(exclude)
        except ValueError:
            pass
        name, status = QInputDialog.getText(self, title, self.tr('Enter notebook name:'))
        while name in names and status:
            message = self.tr('Notebook with this name already exist. Enter notebook name')
            name, status = QInputDialog.getText(self, title, message)
        return name, status


class QNotebookItem(QStandardItem):
    def __init__(self, notebook, count):
        super(QNotebookItem, self).__init__(QIcon.fromTheme('folder'), '%s (%d)' % (notebook.name, count))
        self.notebook = notebook


class QNoteItem(QStandardItem):
    def __init__(self, note):
        super(QNoteItem, self).__init__(QIcon.fromTheme('x-office-document'), note.title)
        self.note = note
