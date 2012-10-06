import sys
sys.path.append('../..')
from PySide.QtGui import (
    QMainWindow, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction, QFileDialog,
    QMenu, QCompleter, QStringListModel,
    QTextCharFormat, QShortcut, QKeySequence,
    QDialog, QInputDialog,
)
from PySide.QtCore import Slot, Qt, QPoint, QObject, Signal, QUrl
from PySide.QtWebKit import QWebPage
from everpad.interface.editor import Ui_Editor
from everpad.interface.image import Ui_ImageDialog
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
import hashlib
import urllib
import json


class ImagePrefs(QDialog):
    def __init__(self, app, res, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.app = app
        self.res = res
        self.ui = Ui_ImageDialog()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.ui.widthBox.setValue(self.res.w)
        self.ui.heightBox.setValue(self.res.h)
        self.ui.widthBox.valueChanged.connect(self.width_changed)
        self.ui.heightBox.valueChanged.connect(self.height_changed)
        self._auto_change = False

    def get_size(self):
        return self.ui.widthBox.value(), self.ui.heightBox.value()

    @Slot()
    def width_changed(self):
        if self.ui.checkBox.isChecked() and not self._auto_change:
            self._auto_change = True
            self.ui.heightBox.setValue(
                self.ui.widthBox.value() * self.res.h / self.res.w,
            )
        else:
            self._auto_change = False

    @Slot()
    def height_changed(self):
        if self.ui.checkBox.isChecked() and not self._auto_change:
            self._auto_change = True
            self.ui.widthBox.setValue(
                self.ui.heightBox.value() * self.res.w / self.res.h,
            )
        else:
            self._auto_change = False


class Page(QWebPage):
    def __init__(self, edit):
        QWebPage.__init__(self)
        self.current = None
        self.edit = edit
        self.active_image = None
        self.active_link = None

        # This allows JavaScript to call back to Slots, connect to Signals
        # and access/modify Qt props
        self.mainFrame().addToJavaScriptWindowObject("qpage", self)

    @Slot(str)
    def set_current_focus(self, focused):
        self.current = focused

    @Slot()
    def page_changed(self):
        self.edit.page_changed()

    @Slot(str, int, int)
    def set_active_image_info(self, image, width, height):
        self.active_image = image
        self.active_width = width
        self.active_height = height

    @Slot(str)
    def set_active_link(self, url):
        self.active_link = url

    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        print message


class ContentEdit(QObject):
    _allowed_tags = (
        'a', 'abbr', 'acronym', 'address', 'area', 'b', 'bdo',
        'big', 'blockquote', 'br', 'caption', 'center', 'cite',
        'code', 'col', 'colgroup', 'dd', 'del', 'dfn', 'div',
        'dl', 'dt', 'em', 'font', 'h1', 'h2', 'h3', 'h4', 'h5',
        'h6', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'map', 'ol',
        'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
        'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot',
        'th', 'thead', 'title', 'tr', 'tt', 'u', 'ul', 'var', 'xmp',
        'en-media', 'en-todo', 'en-crypt',
    )
    _disallowed_attrs = (
        'id', 'class', 'onclick', 'ondblclick',
        'accesskey', 'data', 'dynsrc', 'tabindex',
    )
    _protocols = (
        'http', 'https', 'file',
    )
    _html = open(os.path.join(
        os.path.dirname(__file__), 'editor.html',
    )).read()

    copy_available = Signal(bool)
    def __init__(self, parent, app, widget, on_change):
        QObject.__init__(self)
        self.parent = parent
        self.app = app
        self.widget = widget
        self.page = Page(self)
        self._on_change = on_change
        self._title = None
        self._content = None
        self._hovered_url = None
        self.widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.widget.customContextMenuRequested.connect(self.context_menu)
        for key, action in (
            ('Ctrl+b', QWebPage.ToggleBold),
            ('Ctrl+i', QWebPage.ToggleItalic), 
            ('Ctrl+u', QWebPage.ToggleUnderline),
        ):
            QShortcut(
                QKeySequence(self.app.tr(key)),
                self.widget,
            ).activated.connect(
                Slot()(partial(self._action_for_key, action)),
            )

    @property
    def title(self):
        """Cache title and return"""
        soup = BeautifulSoup(self.page.mainFrame().toHtml())
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
        soup = BeautifulSoup(self.page.mainFrame().toHtml())
        for todo in soup.findAll('input', {'type': 'checkbox'}):
            todo.name = 'en-todo'
            if todo.get('checked') == 'false':
                del todo['checked']
            del todo['type']
        for media in soup.findAll('img'):
            if media.get('class') == 'tab':
                media.replaceWith('\t')
            if media.get('hash'):
                media.name = 'en-media'
                del media['src']
        self._content = reduce(
             lambda txt, cur: txt + unicode(cur),
             self._sanitize(soup.find(id='content')).contents, 
        u'').replace('\n', '')
        return self._content

    @content.setter
    def content(self, val):
        """Set content"""
        soup = BeautifulSoup(val)
        for todo in soup.findAll('en-todo'):
            todo.name = 'input'
            todo['type'] = 'checkbox'
            self.changed_by_default = True
        for media in soup.findAll('en-media'):
            if media.get('hash'):  # evernote android app error
                media.name = 'img'
                res = self.parent.resource_edit.get_by_hash(media['hash'])  # shit!
                if res:
                    media['src'] = 'file://%s' % res.file_path
                    res.in_content = True
                else:
                    media['src'] = ''
            else:
                media.hidden = True
        self._content = unicode(soup).replace('\t', '<img class="tab" />')  # shit!
        self.apply()

    def _sanitize(self, soup):  # TODO: optimize it
        for tag in soup.findAll(True):
            if tag.name in self._allowed_tags:
                for attr in self._disallowed_attrs:
                    try:
                        del tag[attr]
                    except KeyError:
                        pass
                try:
                    if not sum(map(
                        lambda proto: tag['href'].find(proto + '://') == 0, 
                    self._protocols)):
                        del tag['href']
                except KeyError:
                    pass
            else:
                tag.hidden = True
        return soup

    def apply(self):
        """Apply title and content when filled"""
        if None not in (self._title, self._content):
            self.page.mainFrame().setHtml(self._html % {
                'title': self._title, 
                'content': self._content,
            })
            self.widget.setPage(self.page)
            self.page.selectionChanged.connect(self.selection_changed)
            self.page.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
            self.page.linkClicked.connect(self.link_clicked)
            self.page.linkHovered.connect(self.link_hovered)
            self.page.contentsChanged.connect(self.page_changed)

    @Slot()
    def selection_changed(self):
        self.copy_available.emit(
            self.page.current == 'body'
        )
   
    @Slot(QUrl)
    def link_clicked(self, url):
        webbrowser.open(url.toString())

    @Slot(QPoint)
    def context_menu(self, pos, image_hash=None):
        """Show custom context menu"""
        menu = self.page.createStandardContextMenu()
        menu.clear()
        menu.addAction(self.page.action(QWebPage.Cut))
        menu.addAction(self.page.action(QWebPage.Copy))
        menu.addAction(self.page.action(QWebPage.Paste))
        paste_wo = self.page.action(QWebPage.PasteAndMatchStyle)
        paste_wo.setText(self.app.tr('Paste as Plain Text'))
        menu.addAction(paste_wo)
        if self._hovered_url:
            menu.addAction(self.page.action(QWebPage.CopyLinkToClipboard))
            change_link = QAction('Change link', self)
            change_link.triggered.connect(
                Slot()(partial(self._change_link, self.page.active_link)),
            )
            menu.addAction(change_link)
            remove_link = QAction('Remove link', self)
            remove_link.triggered.connect(
                self._remove_link,
            )
            menu.addAction(remove_link)
            self.page.active_link = None
        if self.page.active_image:
            res = self.parent.resource_edit.get_by_hash(self.page.active_image)
            self.page.active_image = None
            menu.addAction(
                self.app.tr('Image Preferences'),
                Slot()(partial(self._show_image_dialog, res)),
            )
        menu.addSeparator()
        menu.addAction(self.page.action(QWebPage.RemoveFormat))
        menu.addAction(self.page.action(QWebPage.SelectAll))
        menu.exec_(self.widget.mapToGlobal(pos))

    @Slot(unicode, unicode, unicode)
    def link_hovered(self, link, title, text):
        self._hovered_url = link

    @Slot()
    def page_changed(self):
        self._on_change()

    def _action_with_icon(self, action_type, icon_name, is_action=False):
        if is_action:
            action = action_type
        else:
            action = self.page.action(action_type)
        action.setIcon(QIcon.fromTheme(icon_name))
        self.copy_available.connect(action.setEnabled)
        return action

    def _action_for_key(self, action):
        if self.page.current == 'body':
            self.page.action(action).trigger()

    @Slot()
    def _insert_link(self):
        url, ok = QInputDialog.getText(self.parent, 
            self.app.tr('Everpad / Insert link'),
            self.app.tr('Press link address'),
        )
        if ok and url:
            self.page.mainFrame().evaluateJavaScript(
                'insertLink(%s);' % json.dumps(url),
            )
            self.page_changed()

    def _change_link(self, url):
        url, ok = QInputDialog.getText(self.parent, 
            self.app.tr('Everpad / Change link'),
            self.app.tr('Press new link address'),
            text=url,
        )
        if ok and url:
            self.page.mainFrame().evaluateJavaScript(
                'changeLink(%s);' % json.dumps(url),
            )
            self.page_changed()

    @Slot()
    def _remove_link(self):
        self.page.mainFrame().evaluateJavaScript(
            'removeLink();',
        )
        self.page_changed()

    @Slot()
    def _insert_check(self):
        self.page.mainFrame().evaluateJavaScript(
            'insertCheck();',
        )
        self.page_changed()

    def get_format_actions(self):
        check_action = QAction(
            self.app.tr('Insert Checkbox'), self,
        )
        check_action.triggered.connect(self._insert_check)
        link_action = QAction(
            self.app.tr('Insert Link'), self,
        )
        link_action.triggered.connect(self._insert_link)
        return map(lambda action: self._action_with_icon(*action), (
            (QWebPage.ToggleBold, 'everpad-text-bold'),
            (QWebPage.ToggleItalic, 'everpad-text-italic'),
            (QWebPage.ToggleUnderline, 'everpad-text-underline'),
            (QWebPage.ToggleStrikethrough, 'everpad-text-strikethrough'),
            (QWebPage.AlignCenter, 'everpad-justify-center'),
            (QWebPage.AlignJustified, 'everpad-justify-fill'),
            (QWebPage.AlignLeft, 'everpad-justify-left'),
            (QWebPage.AlignRight, 'everpad-justify-right'),
            (QWebPage.InsertUnorderedList, 'everpad-list-unordered'),
            (QWebPage.InsertOrderedList, 'everpad-list-ordered'),
            (check_action, 'everpad-checkbox', True),
            (link_action, 'everpad-link', True),
        ))

    def paste_res(self, res):
        self.page.mainFrame().evaluateJavaScript(
            'insertRes("%s", "%s", "%s");' % (
                res.file_path,
                res.hash, res.mime,
            ),
        )
        self.page_changed()

    def _show_image_dialog(self, res):
        res.w = int(self.page.active_width)
        res.h = int(self.page.active_height)
        dialog = ImagePrefs(self.app, res, self.parent)
        if dialog.exec_():
            w, h = dialog.get_size()
            self.page.mainFrame().evaluateJavaScript(
                'changeRes("%s", %d, %d);' % (
                    res.hash, w, h,
                ),
            )
            self.page_changed()


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
        self._res_hash = {}
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
        self._res_hash[res.hash] = res
        res.in_content = False

    def get_by_hash(self, hash):
        return self._res_hash.get(hash)

    def click(self, res, event):
        """Open resource"""
        button = event.button()
        if button == Qt.LeftButton:
            subprocess.Popen(['xdg-open', res.file_path])
        elif button == Qt.RightButton:
            menu = QMenu(self.parent)
            if res.mime.find('image') == 0:
                menu.addAction(
                    self.parent.tr('Put to Content'), Slot()(partial(
                        self.to_content, res=res,
                    )),
                )
            if not res.in_content:
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

    def to_content(self, res):
        res.in_content = True
        self.parent.note_edit.paste_res(res)

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
        if os.path.isfile(name):
            shutil.copyfile(name, file_path)
        else:
            with open(file_path, 'w') as res_file:
                res_file.write(urllib.urlopen(name).read())
        res = Resource(
            id=NONE_ID,
            file_path=file_path,
            file_name=file_name,
            mime=self.mime.file(file_path.encode('utf8')),
            hash=hashlib.md5(open(file_path).read()).hexdigest(),
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
        self.update_title()
        self.mark_untouched()
        geometry = self.app.settings.value("note-geometry-%d" % self.note.id)
        if geometry:
            self.restoreGeometry(geometry)
        self.resource_edit.note = note

    def init_controls(self):
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
        self.init_toolbar()

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
        for action in self.note_edit.get_format_actions():
            self.ui.toolBar.addAction(action)
        self.ui.toolBar.addSeparator()
        self.ui.toolBar.addAction(
            QIcon.fromTheme('add'), self.tr('Attach file'),
            self.resource_edit.add,
        )
        self.ui.toolBar.addSeparator()

    def load_note(self, note):
        self.note = note
        self.resource_edit.resources = map(Resource.from_tuple,
            self.app.provider.get_note_resources(note.id),
        )
        self.notebook_edit.notebook = note.notebook
        self.note_edit.title = note.title
        self.note_edit.content = note.content
        self.tag_edit.tags = note.tags

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

    def text_changed(self):
        self.update_title()
        self.mark_touched()

    def update_title(self):
        self.setWindowTitle(u'Everpad / %s' % self.note_edit.title)

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
            self.tr("You are trying to delete a note"),
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

    @Slot()
    def mark_touched(self):
        self.touched = True
        self.ui.actionSave.setEnabled(True)
        self.save_btn.setEnabled(True)

    def mark_untouched(self):
        self.touched = False
        self.ui.actionSave.setEnabled(False)
        self.save_btn.setEnabled(False)
