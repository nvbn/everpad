import sys
sys.path.append('../..')
from PySide.QtGui import QMainWindow, QIcon
from PySide.QtCore import Slot
from everpad.interface.editor import Ui_Editor
from everpad.pad.tools import get_icon
from everpad.tools import get_provider
from everpad.basetypes import Note, Notebook
from BeautifulSoup import BeautifulSoup
import dbus


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

    def init_controls(self):
        self.ui.tags.hide()
        self.ui.notebook.hide()
        self.ui.menubar.hide()
        self.ui.content.textChanged.connect(self.text_changed)
        self.init_menu()
        self.init_toolbar()
        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            self.ui.notebook.addItem(notebook.name, userData=notebook.id)

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
        self.ui.toolBar.addAction(
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
        self.update_note()
        self.app.provider.delete_note(self.note.id)
        self.app.send_notify(u'Note "%s" deleted!' % self.note.title)
        self.close()

    @Slot()
    def close(self):
        self.hide()
        self.closed = True
