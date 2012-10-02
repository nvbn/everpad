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
from PySide.QtCore import Slot, Qt, QPoint
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
        self.ui.notebooksList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.notebooksList.customContextMenuRequested.connect(self.notebook_context_menu)

        self.notesModel = QStandardItemModel()
        self.ui.notesList.setModel(self.notesModel)
        self.ui.notesList.doubleClicked.connect(self.note_dblclicked)
        self.ui.notesList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.notesList.customContextMenuRequested.connect(self.note_context_menu)

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
    def rename_notebook(self):
        index = self.ui.notebooksList.currentIndex()
        item = self.notebooksModel.itemFromIndex(index)
        notebook = item.notebook
        name, status = self._notebook_new_name(
            self.tr('Rename notebook'), notebook.name,
        )
        if status:
            notebook.name = name
            self.app.provider.update_notebook(notebook.struct)
            self.app.send_notify(self.tr('Notebook "%s" renamed!') % notebook.name)
            self._reload_notebooks_list(notebook.id)

    @Slot()
    def remove_notebook(self):
        msg = QMessageBox(
            QMessageBox.Critical,
            self.tr("You are trying to delete a notebook"),
            self.tr("Are you sure want to delete this notebook and its notes?"),
            QMessageBox.Yes | QMessageBox.No
        )
        if msg.exec_() == QMessageBox.Yes:
            index = self.ui.notebooksList.currentIndex()
            item = self.notebooksModel.itemFromIndex(index)
            self.app.provider.delete_notebook(item.notebook.id)
            self.app.send_notify(self.tr('Notebook "%s" deleted!') % item.notebook.name)
            self._reload_notebooks_list()

    @Slot()
    def new_note(self):
        index = self.ui.notebooksList.currentIndex()
        notebook_id = NONE_ID
        if index.row():
            item = self.notebooksModel.itemFromIndex(index)
            notebook_id = item.notebook.id

        self.app.indicator.create(notebook_id=notebook_id)

    @Slot()
    def edit_note(self):
        index = self.ui.notesList.currentIndex()
        item = self.notesModel.itemFromIndex(index)
        self.app.indicator.open(item.note)

    @Slot()
    def remove_note(self):
        index = self.ui.notesList.currentIndex()
        item = self.notesModel.itemFromIndex(index)
        msgBox = QMessageBox(
            QMessageBox.Critical,
            self.tr("You are trying to delete a note"),
            self.tr('Are you sure want to delete note "%s"?') % item.note.title,
            QMessageBox.Yes | QMessageBox.No
        )
        if msgBox.exec_() == QMessageBox.Yes:
            self.app.provider.delete_note(item.note.id)
            self.app.send_notify(self.tr('Note "%s" deleted!') % item.note.title)
            self.notebook_selected(self.ui.notebooksList.currentIndex())

    @Slot(QPoint)
    def notebook_context_menu(self, pos):
        if self.ui.notebooksList.currentIndex().row():
            menu = QMenu(self.ui.notebooksList)
            menu.addAction(QIcon.fromTheme('gtk-edit'), self.tr('Rename'), self.rename_notebook)
            menu.addAction(QIcon.fromTheme('gtk-delete'), self.tr('Remove'), self.remove_notebook)
            menu.exec_(self.ui.notebooksList.mapToGlobal(pos))

    @Slot(QPoint)
    def note_context_menu(self, pos):
        menu = QMenu(self.ui.notesList)
        menu.addAction(QIcon.fromTheme('gtk-edit'), self.tr('Edit'), self.edit_note)
        menu.addAction(QIcon.fromTheme('gtk-delete'), self.tr('Remove'), self.remove_note)
        menu.exec_(self.ui.notesList.mapToGlobal(pos))

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
        name, status = QInputDialog.getText(self, title, self.tr('Enter notebook name:'), text=exclude)
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
