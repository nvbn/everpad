import sys
sys.path.append('../..')
from PySide.QtGui import (
    QMainWindow, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction, QFileDialog,
    QMenu, QCompleter, QStringListModel,
    QTextCharFormat,
)
from PySide.QtCore import Slot, Qt, QPoint, QObject, Signal, QUrl
from PySide.QtWebKit import QWebPage
from everpad.interface.editor import Ui_Editor
from everpad.pad.tools import get_icon
from everpad.tools import get_provider
from everpad.basetypes import Note, Notebook, Resource, NONE_ID, Tag
from BeautifulSoup import BeautifulSoup
from functools import partial
import dbus
import subprocess
import webbrowser
import magic
import os
import shutil

html = """
<!DOCTYPE html>
<html>
<body>
<form>
<h2 contenteditable="true" id='title'>%(title)s</h2>
<div contenteditable="true" id='content'>%(content)s</div>
</form>
</body>
</html>
"""


class ContentEdit(QObject):
    copy_available = Signal(bool)
    def __init__(self, parent, app, widget, on_change):
        QObject.__init__(self)
        self.parent = parent
        self.app = app
        self.widget = widget
        self._on_change = on_change
        self._title = None
        self._content = None
        self._hovered_url = None
        self.widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.widget.customContextMenuRequested.connect(self.context_menu)

    @property
    def title(self):
        """Cache title and return"""
        soup = BeautifulSoup(self.widget.page().mainFrame().toHtml())
        self._title = soup.find(id='title').text
        return self._title

    @title.setter
    def title(self, val):
        """Set title"""
        self._title = val
        self.apply()

    @property
    def content(self):
        """Cache content and return"""
        soup = BeautifulSoup(self.widget.page().mainFrame().toHtml())
        for todo in soup.findAll('input', {'type': 'checkbox'}):
            todo.name = 'en-todo'
            del todo['type']
        self._content = reduce(
             lambda txt, cur: txt + unicode(cur),
             soup.find(id='content').contents, 
        u'')
        return self._content

    @content.setter
    def content(self, val):
        """Set content"""
        soup = BeautifulSoup(val)
        for todo in soup.findAll('en-todo'):
            todo.name = 'input'
            todo['type'] = 'checkbox'
            self.changed_by_default = True
        self._content = unicode(soup)
        self.apply()

    def apply(self):
        """Apply title and content when filled"""
        if self._title and self._content:
            self.widget.setHtml(html % {
                'title': self._title, 
                'content': self._content,
            })
            page = self.widget.page()
            page.selectionChanged.connect(self.selection_changed)
            page.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
            page.linkClicked.connect(self.link_clicked)
            page.linkHovered.connect(self.link_hovered)
            page.contentsChanged.connect(self.page_changed)

    @Slot()
    def selection_changed(self):
        self.copy_available.emit(len(self.widget.page().selectedText()) > 0)

    @Slot()
    def copy(self):
        self.widget.page().action(QWebPage.Copy).trigger()

    @Slot()
    def cut(self):
        self.widget.page().action(QWebPage.Cut).trigger()

    @Slot()
    def paste(self):
        self.widget.page().action(QWebPage.Paste).trigger()

    @Slot()
    def select_all(self):
        self.widget.page().action(QWebPage.SelectAll).trigger()

    @Slot(QUrl)
    def link_clicked(self, url):
        webbrowser.open(url.toString())

    @Slot(QPoint)
    def context_menu(self, pos):
        """Show custom context menu"""
        menu = self.widget.page().createStandardContextMenu()
        menu.clear()
        menu.addAction(self.widget.page().action(QWebPage.Cut))
        menu.addAction(self.widget.page().action(QWebPage.Copy))
        menu.addAction(self.widget.page().action(QWebPage.Paste))
        if self._hovered_url:
            menu.addAction(self.widget.page().action(QWebPage.CopyLinkToClipboard))
        menu.addSeparator()
        menu.addAction(self.widget.page().action(QWebPage.SelectAll))
        menu.exec_(self.widget.mapToGlobal(pos))

    @Slot(unicode, unicode, unicode)
    def link_hovered(self, link, title, text):
        self._hovered_url = link

    @Slot()
    def page_changed(self):
        self._on_change()


class TagEdit(object):
    """Abstraction for tag edit"""

    def __init__(self, parent, app, widget, on_change):
        """Init and connect signals"""
        self.parent = parent
        self.app = app
        self.widget = widget
        self.tags_list = map(lambda tag:
            Tag.from_tuple(tag).name,
            self.app.provider.list_tags(),
        )
        self.completer = QCompleter()
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.completer.activated.connect(self.update_completion)
        self.update_completion()
        self.widget.setCompleter(self.completer)
        self.widget.textChanged.connect(Slot()(on_change))
        self.widget.textEdited.connect(self.update_completion)

    @property
    def tags(self):
        """Get tags"""
        return map(lambda tag: tag.strip(),
            self.widget.text().split(','))

    @tags.setter
    def tags(self, val):
        """Set tags"""
        self.widget.setText(', '.join(val))

    @Slot()
    def update_completion(self):
        """Update completion model with exist tags"""
        orig_text = self.widget.text()
        text = ', '.join(orig_text.replace(', ', ',').split(',')[:-1])
        tags = []
        for tag in self.tags_list:
            if ',' in orig_text:
                if orig_text[-1] not in (',', ' '):
                    tags.append('%s,%s' % (text, tag))
                tags.append('%s, %s' % (text, tag))
            else:
                tags.append(tag)
        if tags != self.completer_model.stringList():
            self.completer_model.setStringList(tags)


class NotebookEdit(object):
    """Abstraction for notebook edit"""

    def __init__(self, parent, app, widget, on_change):
        """Init and connect signals"""
        self.parent = parent
        self.app = app
        self.widget = widget
        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            self.widget.addItem(notebook.name, userData=notebook.id)
        self.widget.currentIndexChanged.connect(Slot()(on_change))

    @property
    def notebook(self):
        """Get notebook"""
        notebook_index = self.widget.currentIndex()
        return self.widget.itemData(notebook_index)

    @notebook.setter
    def notebook(self, val):
        """Set notebook"""
        notebook_index = self.widget.findData(val)
        self.widget.setCurrentIndex(notebook_index)


class ResourceEdit(object):
    """Abstraction for notebook edit"""

    def __init__(self, parent, app, widget, on_change):
        """Init and connect signals"""
        self.parent = parent
        self.app = app
        self.widget = widget
        self.note = None
        self.on_change = on_change
        self._resource_labels = {}
        self._resources = []
        frame = QFrame()
        frame.setLayout(QVBoxLayout())
        frame.setFixedWidth(100)
        self.widget.setFixedWidth(100)
        self.widget.setWidget(frame)
        self.widget.hide()
        self.mime = magic.open(magic.MIME_TYPE)
        self.mime.load()

    @property
    def resources(self):
        """Get resources"""
        return self._resources

    @resources.setter
    def resources(self, val):
        """Set resources"""
        self._resources = val
        for res in val:
            self._put(res)

    def _put(self, res):
        """Put resource on widget"""
        label = QLabel()
        if 'image' in res.mime:
            pixmap = QPixmap(res.file_path).scaledToWidth(100)
            label.setPixmap(pixmap)
            label.setMask(pixmap.mask())
        else:
            label.setText(res.file_name)
        label.mouseReleaseEvent = partial(self.click, res)
        self.widget.widget().layout().addWidget(label)
        self.widget.show()
        self._resource_labels[res] = label

    def click(self, res, event):
        """Open resource"""
        button = event.button()
        if button == Qt.LeftButton:
            subprocess.Popen(['xdg-open', res.file_path])
        elif button == Qt.RightButton:
            menu = QMenu(self.parent)
            menu.addAction(
                self.parent.tr('Remove Resource'), Slot()(partial(
                    self.remove, res=res,
                ))
            )
            menu.addAction(
                self.parent.tr('Save As'), Slot()(partial(
                    self.save, res=res,
                ))
            )
            menu.exec_(event.globalPos())

    def remove(self, res):
        """Remove resource"""
        msg_box = QMessageBox(
            QMessageBox.Critical,
            self.parent.tr("You try to delete resource"),
            self.parent.tr("Are you sure want to delete this resource?"),
            QMessageBox.Yes | QMessageBox.No
        )
        ret = msg_box.exec_()
        if ret == QMessageBox.Yes:
            self._resources.remove(res)
            self._resource_labels[res].hide()
            del self._resource_labels[res]
            self.on_change()
            if not self._resources:
                self.widget.hide()

    def save(self, res):
        """Save resource"""
        name, filters = QFileDialog.getSaveFileName()
        if name:
            shutil.copyfile(res.file_path, name)

    @Slot()
    def add(self):
        for name in QFileDialog.getOpenFileNames()[0]:
            self.add_attach(name)


    def add_attach(self, name):
        dest = os.path.expanduser('~/.everpad/data/%d/' % self.note.id)
        try:
            os.mkdir(dest)
        except OSError:
            pass
        file_name = name.split('/')[-1]
        file_path = os.path.join(dest, file_name)
        shutil.copyfile(name, file_path)
        res = Resource(
            id=NONE_ID,
            file_path=file_path,
            file_name=file_name,
            mime=self.mime.file(file_path.encode('utf8')),
        )
        self._resources.append(res)
        self._put(res)
        self.on_change()


class Editor(QMainWindow):  # TODO: kill this god shit
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
        self.resource_edit.note = note

    def init_controls(self):
        self.ui.tags.hide()
        self.ui.notebook.hide()
        self.ui.menubar.hide()
        self.ui.resourceArea.hide()
        self.note_edit = ContentEdit(
            self, self.app, 
            self.ui.contentView, self.text_changed,
        )
        self.tag_edit = TagEdit(
            self, self.app, 
            self.ui.tags, self.mark_touched,
        )
        self.notebook_edit = NotebookEdit(
            self, self.app, 
            self.ui.notebook, self.mark_touched,
        )
        self.resource_edit = ResourceEdit(
            self, self.app, 
            self.ui.resourceArea, self.mark_touched,
        )
        self.init_menu()
        self.init_toolbar()

    def init_menu(self):
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSave_and_close.triggered.connect(self.save_and_close)
        self.ui.actionDelete.triggered.connect(self.delete)
        self.ui.actionClose.triggered.connect(self.close)
        self.note_edit.copy_available.connect(self.ui.actionCopy.setEnabled)
        self.ui.actionCopy.setEnabled(False)
        self.ui.actionCopy.triggered.connect(self.note_edit.copy)
        self.note_edit.copy_available.connect(self.ui.actionCut.setEnabled)
        self.ui.actionCut.setEnabled(False)
        self.ui.actionCut.triggered.connect(self.note_edit.cut)
        self.ui.actionPaste.triggered.connect(self.note_edit.paste)

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
            self.note_edit.cut,
        )
        self.note_edit.copy_available.connect(cut.setEnabled)
        cut.setEnabled(False)
        copy = self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-copy'), self.tr('Copy'),
            self.note_edit.copy,
        )
        self.note_edit.copy_available.connect(copy.setEnabled)
        copy.setEnabled(False)
        self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-paste'), self.tr('Paste'),
            self.note_edit.paste,
        )
        self.ui.toolBar.addSeparator()
        self.ui.toolBar.addAction(
            QIcon.fromTheme('add'), self.tr('Attache file'),
            self.resource_edit.add,
        )
        self.ui.toolBar.addSeparator()
        self.options = self.ui.toolBar.addAction(
            QIcon.fromTheme('gtk-properties'), 
            self.tr('Options'), self.show_options,
        )
        self.options.setCheckable(True)

    def load_note(self, note):
        self.note = note
        self.notebook_edit.notebook = note.notebook
        self.note_edit.title = note.title
        self.note_edit.content = note.content
        self.tag_edit.tags = note.tags
        self.resource_edit.resources = map(Resource.from_tuple,
            self.app.provider.get_note_resources(note.id),
        )

    def update_note(self):
        self.note.notebook = self.notebook_edit.notebook
        self.note.title = self.note_edit.title
        self.note.content = self.note_edit.content
        self.note.tags = dbus.Array(self.tag_edit.tags, signature='s')

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

    def text_changed(self):
        self.setWindowTitle(u'Everpad / %s' % self.note_edit.title)
        self.mark_touched()

    @Slot()
    def save(self):
        self.mark_untouched()
        self.update_note()
        self.app.provider.update_note(self.note.struct)
        self.app.provider.update_note_resources(
            self.note.struct, dbus.Array(map(lambda res:
                res.struct, self.resource_edit.resources,
            ), signature=Resource.signature),
        )
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

    @Slot()
    def mark_touched(self):
        self.touched = True
        self.ui.actionSave.setEnabled(True)
        self.save_btn.setEnabled(True)

    def mark_untouched(self):
        self.touched = False
        self.ui.actionSave.setEnabled(False)
        self.save_btn.setEnabled(False)
