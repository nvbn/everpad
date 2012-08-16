import sys
sys.path.append('../..')
from PySide.QtGui import (
    QMainWindow, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction,
)
from PySide.QtCore import Slot, Qt, QPoint
from everpad.interface.editor import Ui_Editor
from everpad.pad.tools import get_icon
from everpad.tools import get_provider
from everpad.basetypes import Note, Notebook, Resource
from BeautifulSoup import BeautifulSoup
from functools import partial
import dbus
import subprocess
import webbrowser


class Editor(QMainWindow):
    """Note editor"""

    def __init__(self, app, note, *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        self.app = app
        self.closed = False
        self.ui = Ui_Editor()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.init_controls()
        self.load_note(note)
        self.mark_untouched()
        geometry = self.app.settings.value("note-geometry-%d" % self.note.id)
        if geometry:
            self.restoreGeometry(geometry)
        options = self.app.settings.value('note-options-%d' % self.note.id)
        if options:
            self.options.setChecked(True)
            self.show_options()

    def init_controls(self):
        self.ui.tags.hide()
        self.ui.notebook.hide()
        self.ui.menubar.hide()
        self.ui.content.textChanged.connect(self.text_changed)
        self.ui.resourceArea.hide()
        self.init_menu()
        self.init_toolbar()
        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            self.ui.notebook.addItem(notebook.name, userData=notebook.id)
        frame = QFrame()
        frame.setLayout(QVBoxLayout())
        frame.setFixedWidth(100)
        self.ui.resourceArea.setFixedWidth(100)
        self.ui.resourceArea.setWidget(frame)
        self.ui.resourceArea.hide()
        self.ui.tags.textChanged.connect(self.mark_touched)
        self.ui.notebook.currentIndexChanged.connect(self.mark_touched)
        self.ui.content.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.content.customContextMenuRequested.connect(self.context_menu)

    def init_menu(self):
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSave_and_close.triggered.connect(self.save_and_close)
        self.ui.actionDelete.triggered.connect(self.delete)
        self.ui.actionClose.triggered.connect(self.close)
        self.ui.content.copyAvailable.connect(self.ui.actionCopy.setEnabled)
        self.ui.actionCopy.setEnabled(False)
        self.ui.actionCopy.triggered.connect(self.ui.content.copy)
        self.ui.content.copyAvailable.connect(self.ui.actionCut.setEnabled)
        self.ui.actionCut.setEnabled(False)
        self.ui.actionCut.triggered.connect(self.ui.content.cut)
        self.ui.actionPaste.triggered.connect(self.ui.content.paste)

    def init_toolbar(self):
        self.save_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('document-save'), 
            self.tr('Save'), self.save,
        )
        self.ui.toolBar.addAction(
            QIcon.fromTheme('cancel'), 
            self.tr('Close without saving'), 
            self.close,
        )
        self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-delete'),
            self.tr('Remove note'), 
            self.delete,
        )
        self.ui.toolBar.addSeparator()
        cut = self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-cut'), self.tr('Cut'),
            self.ui.content.cut,
        )
        self.ui.content.copyAvailable.connect(cut.setEnabled)
        cut.setEnabled(False)
        copy = self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-copy'), self.tr('Copy'),
            self.ui.content.copy,
        )
        self.ui.content.copyAvailable.connect(copy.setEnabled)
        copy.setEnabled(False)
        self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-paste'), self.tr('Paste'),
            self.ui.content.paste,
        )
        self.ui.toolBar.addSeparator()
        self.options = self.ui.toolBar.addAction(
            QIcon.fromTheme('gtk-properties'), 
            self.tr('Options'), self.show_options,
        )
        self.options.setCheckable(True)

    def load_note(self, note):
        self.note = note
        notebook_index = self.ui.notebook.findData(note.notebook)
        self.ui.notebook.setCurrentIndex(notebook_index)
        self.ui.content.setHtml("<h2>%s</h2><a href='#' />\n%s" % (
            note.title, note.content,
        ))
        self.ui.tags.setText(', '.join(note.tags))
        self.resources = map(Resource.from_tuple,
            self.app.provider.get_note_resources(note.id),
        )
        if self.resources:
            self.ui.resourceArea.show()
            for res in self.resources:
                label = QLabel()
                if 'image' in res.mime:
                    pixmap = QPixmap(res.file_path).scaledToWidth(100)
                    label.setPixmap(pixmap)
                    label.setMask(pixmap.mask())
                else:
                    label.setText(res.file_name)
                label.mouseReleaseEvent = partial(self.open_res, res.file_path)
                self.ui.resourceArea.widget().layout().addWidget(label)

    def update_note(self):
        notebook_index = self.ui.notebook.currentIndex()
        self.note.notebook = self.ui.notebook.itemData(notebook_index)
        self.note.title = self.get_title()
        soup = BeautifulSoup(self.ui.content.toHtml())
        self.note.content = reduce(
            lambda txt, cur: txt + unicode(cur),
            soup.find('body').contents[2:], 
        u'')
        self.note.tags = dbus.Array(map(
            lambda tag: tag.strip(),
            self.ui.tags.text().split(','),
        ), signature='s')

    def get_title(self):
        return self.ui.content.toPlainText().split('\n')[0]

    def closeEvent(self, event):
        event.ignore()
        if self.touched:
            self.save()
        self.close()

    @Slot()
    def show_options(self):
        if self.options.isChecked():  # action checked after emit
            self.ui.tags.show()
            self.ui.notebook.show()
        else:
            self.ui.tags.hide()
            self.ui.notebook.hide()

    @Slot()
    def text_changed(self):
        self.setWindowTitle(u'Everpad / %s' % self.get_title())
        self.mark_touched()

    @Slot()
    def save(self):
        self.update_note()
        self.app.provider.update_note(self.note.struct)
        self.app.send_notify(u'Note "%s" saved!' % self.note.title)

    @Slot()
    def save_and_close(self):
        self.save()
        self.close()

    @Slot()
    def delete(self):
        msgBox = QMessageBox(
            QMessageBox.Critical,
            self.tr("You try to delete a note"),
            self.tr("Are you sure want to delete this note?"),
            QMessageBox.Yes | QMessageBox.No
        )
        ret = msgBox.exec_()
        if ret == QMessageBox.Yes:
            self.update_note()
            self.app.provider.delete_note(self.note.id)
            self.app.send_notify(u'Note "%s" deleted!' % self.note.title)
            self.close()

    @Slot()
    def close(self):
        self.hide()
        self.closed = True
        self.app.settings.setValue(
            "note-geometry-%d" % self.note.id, 
            self.saveGeometry(),
        )
        self.app.settings.setValue(
            'note-options-%d' % self.note.id,
            self.options.isChecked(),
        )

    def open_res(self, path, *args):  # event
        subprocess.Popen(['xdg-open', path])

    @Slot()
    def mark_touched(self):
        self.touched = True
        self.ui.actionSave.setEnabled(True)
        self.save_btn.setEnabled(True)

    def mark_untouched(self):
        self.touched = False
        self.ui.actionSave.setEnabled(False)
        self.save_btn.setEnabled(False)

    @Slot(QPoint)
    def context_menu(self, pos):
        menu = self.ui.content.createStandardContextMenu(pos)
        cursor = self.ui.content.cursorForPosition(pos)
        char_format = cursor.charFormat()
        if char_format.isAnchor():
            url = char_format.anchorHref()
            open_action = QAction(self.tr("Open Link"), menu)
            open_action.triggered.connect(Slot()(lambda: webbrowser.open(url)))
            copy_action = QAction(self.tr("Copy Link"), menu)
            copy_action.triggered.connect(Slot()(lambda: self.app.clipboard().setText(url)))
            menu.insertAction(menu.actions()[0], open_action)
            menu.insertAction(menu.actions()[0], copy_action)
            menu.insertSeparator(menu.actions()[2])
        menu.exec_(self.ui.content.mapToGlobal(pos))
