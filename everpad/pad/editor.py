import sys
sys.path.append('../..')
from PySide.QtGui import (
    QMainWindow, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction, QFileDialog,
    QMenu, QCompleter, QStringListModel,
    QTextCharFormat, QShortcut, QKeySequence,
    QDialog, QInputDialog, QFileIconProvider,
    QWidget, QScrollArea, QFont, QHBoxLayout,
)
from PySide.QtCore import (
    Slot, Qt, QPoint, QObject, Signal, QUrl,
    QFileInfo, 
)
from PySide.QtWebKit import QWebPage, QWebSettings
from everpad.interface.editor import Ui_Editor
from everpad.interface.image import Ui_ImageDialog
from everpad.interface.tableinsert import Ui_TableInsertDialog 
from everpad.interface.findbar import Ui_FindBar
from everpad.pad.tools import get_icon
from everpad.tools import get_provider, sanitize, clean, html_unescape
from everpad.basetypes import Note, Notebook, Resource, NONE_ID, Tag
from everpad.const import DEFAULT_FONT, DEFAULT_FONT_SIZE
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
import re


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


class TableInsert(QDialog):
    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.ui = Ui_TableInsertDialog()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())

    def get_width(self):
        result = self.ui.width.text()
        # 0 is %, 1 is px.
        if self.ui.widthType.currentIndex() == 0:
            result += '%'
        return result


class FindBar(QWidget):
    def __init__(self, editor, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.editor = editor
        self.ui = Ui_FindBar()
        self.ui.setupUi(self)

        # pyside-uic doesn't translate icons from themes correctly, so we have
        # to re-set the icons manually here
        self.ui.btnPrevious.setIcon(QIcon.fromTheme('go-previous'))
        self.ui.btnNext.setIcon(QIcon.fromTheme('go-next'))
        self.ui.btnClose.setIcon(QIcon.fromTheme('window-close'))
        self.visible = False

        self.ui.btnClose.clicked.connect(self.hide)
        self.ui.edtFindText.returnPressed.connect(self.find_next)
        self.ui.edtFindText.textChanged.connect(self.find_text_updated)

        self.ui.btnNext.clicked.connect(self.find_next)
        self.ui.btnPrevious.clicked.connect(self.find_previous)

        self.ui.btnHighlight.clicked.connect(self.update_highlight)
        self.ui.chkMatchCase.clicked.connect(self.match_case_updated)

    def set_search_term(self, search_term):
        self.ui.edtFindText.setText(search_term)

    def get_flags(self, default_flags=None):
        flags = QWebPage.FindFlag.FindWrapsAroundDocument
        if default_flags is not None:
            flags |= default_flags
        if self.ui.chkMatchCase.isChecked():
            flags |= QWebPage.FindFlag.FindCaseSensitively
        return flags

    @Slot()
    def match_case_updated(self):
        flags = self.get_flags()

        # We need the *old* flags value;  clear this flag if it's checked
        if self.ui.chkMatchCase.isChecked():
            flags &= ~QWebPage.FindFlag.FindCaseSensitively
        else:
            flags |= QWebPage.FindFlag.FindCaseSensitively
        self.update_highlight(flags=flags, clear=True)
        self.update_highlight()

    @Slot(str)
    def find_text_updated(self, text):
        self.update_highlight(text=text, clear=True)
        self.find()

    @Slot()
    def find_next(self, text=None):
        self.find()

    @Slot()
    def find_previous(self):
        self.find(QWebPage.FindFlag.FindBackward)

    def find(self, flags=None):
        if not self.visible:
            self.show(focus=False)
            return

        flags = self.get_flags(flags)
        self.editor.note_edit.page.findText(self.ui.edtFindText.text(), flags)
        self.update_highlight()

    @Slot()
    def update_highlight(self, flags=None, text=None, clear=False):
        flags = flags or self.get_flags()
        flags |= QWebPage.FindFlag.HighlightAllOccurrences
        text = text or self.ui.edtFindText.text()
        if clear or not self.ui.btnHighlight.isChecked():
            text = ''
        self.editor.note_edit.page.findText(text, flags)

    def show(self, flags=None, focus=True):
        QWidget.show(self)
        if self.visible:
            self.find(flags)
        else:
            self.editor.ui.centralwidget.layout().addWidget(self)
            self.visible = True

            self.find(flags)
            self.update_highlight()

        if focus:
            self.ui.edtFindText.setFocus()

        self.editor.find_action.setChecked(True)

    @Slot()
    def hide(self):
        QWidget.hide(self)
        if not self.visible:
            return
        self.update_highlight(clear=True)
        self.editor.ui.centralwidget.layout().removeWidget(self)
        self.setParent(None)
        self.visible = False
        self.editor.find_action.setChecked(False)

    @Slot()
    def toggle_visible(self):
        if self.visible:
            self.hide()
        else:
            self.show()

class Page(QWebPage):
    def __init__(self, edit):
        QWebPage.__init__(self)
        self.current = None
        self.edit = edit
        self.active_image = None
        self.active_link = None
        settings = self.settings()
        family = self.edit.app.settings.value(
            'note-font-family', DEFAULT_FONT,
        )
        size = int(self.edit.app.settings.value(
            'note-font-size', DEFAULT_FONT_SIZE,
        ))
        settings.setFontFamily(
            QWebSettings.StandardFont, family,
        )
        settings.setFontSize(
            QWebSettings.DefaultFontSize, size,
        )
        settings.setFontSize(
            QWebSettings.DefaultFixedFontSize, size,
        )

        # This allows JavaScript to call back to Slots, connect to Signals
        # and access/modify Qt props
        self.mainFrame().addToJavaScriptWindowObject("qpage", self)

    @Slot()
    def show_findbar(self):
        self.edit.parent.findbar.show()

    @Slot()
    def find_next(self):
        self.edit.parent.findbar.find_next()

    @Slot()
    def find_previous(self):
        self.edit.parent.findbar.find_previous()

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
        self._init_shortcuts()

    def _init_shortcuts(self):
        for key, action in (
            ('Ctrl+b', QWebPage.ToggleBold),
            ('Ctrl+i', QWebPage.ToggleItalic), 
            ('Ctrl+u', QWebPage.ToggleUnderline),
            ('Ctrl+Shift+b', QWebPage.InsertUnorderedList),
            ('Ctrl+Shift+o', QWebPage.InsertOrderedList),
            ('Ctrl+shift+v', QWebPage.PasteAndMatchStyle),
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
        return clean(html_unescape(self._title))

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
                media.replaceWith(' ' * 5)
            if media.get('hash'):
                media.name = 'en-media'
                del media['src']
        self._content = sanitize(
            soup=soup.find(id='content'),
        ).replace('  ', u'\xa0 ')
        return self._content

    @content.setter
    def content(self, val):
        """Set content"""
        soup = BeautifulSoup(val)
        for todo in soup.findAll('en-todo'):
            todo.name = 'input'
            todo['type'] = 'checkbox'
            if todo.get('checked') == 'false':
                del todo['checked']
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
        self._content = re.sub(
            r'(&nbsp;| ){5}', '<img class="tab" />', 
            unicode(soup).replace(u'\xa0', ' '),
        )  # shit!
        self.apply()

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

    def _action_with_icon(self, action_type, icon_names, is_action=False):
        if is_action:
            action = action_type
        else:
            action = self.page.action(action_type)
        for icon_name in icon_names:
            if QIcon.hasThemeIcon(icon_name):
                action.setIcon(QIcon.fromTheme(icon_name))
                break

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
    def _insert_table(self):
        dialog = TableInsert(self.parent)
        if dialog.exec_():
            self.page.mainFrame().evaluateJavaScript(
                'insertTable(%s, %s, "%s");' % (
                    dialog.ui.rows.text(),
                    dialog.ui.columns.text(),
                    dialog.get_width(),
                )
            )

    @Slot()
    def _insert_check(self):
        self.page.mainFrame().evaluateJavaScript(
            'insertCheck();',
        )
        self.page_changed()

    @Slot()
    def _insert_image(self):
        name = QFileDialog.getOpenFileName(
            filter=self.app.tr("Image Files (*.png *.jpg *.bmp *.gif)"),
        )[0]
        if name:
            res = self.parent.resource_edit.add_attach(name)
            self.paste_res(res)

    def get_format_actions(self):
        check_action = QAction(
            self.app.tr('Insert Checkbox'), self,
        )
        check_action.triggered.connect(self._insert_check)
        link_action = QAction(
            self.app.tr('Insert Link'), self,
        )
        link_action.triggered.connect(self._insert_link)
        table_action = QAction(
            self.app.tr('Insert Table'), self,
        )
        table_action.triggered.connect(self._insert_table)
        image_action = QAction(
            self.app.tr('Insert Image'), self,
        )
        image_action.triggered.connect(self._insert_image)

        actions = [
            (QWebPage.ToggleBold,
                ['format-text-bold', 'everpad-text-bold']),
            (QWebPage.ToggleItalic,
                ['format-text-italic', 'everpad-text-italic']),
            (QWebPage.ToggleUnderline,
                ['format-text-underline', 'everpad-text-underline']),
            (QWebPage.ToggleStrikethrough,
                ['format-text-strikethrough', 'everpad-text-strikethrough']),
            (QWebPage.AlignCenter,
                ['format-justify-center', 'everpad-justify-center']),
            (QWebPage.AlignJustified,
                ['format-justify-fill', 'everpad-justify-fill']),
            (QWebPage.AlignLeft,
                ['format-justify-left', 'everpad-justify-left']),
            (QWebPage.AlignRight,
                ['format-justify-right', 'everpad-justify-right']),
            ]

        if self._enable_text_direction_support():
            actions += [
                (QWebPage.SetTextDirectionLeftToRight,
                    ['format-text-direction-ltr', 'everpad-text-direction-ltr']),
                (QWebPage.SetTextDirectionRightToLeft,
                    ['format-text-direction-rtl', 'everpad-text-direction-rtl']),
                ]

        actions += [
            (QWebPage.InsertUnorderedList,
                ['format-list-unordered', 'everpad-list-unordered']),
            (QWebPage.InsertOrderedList,
                ['format-list-ordered', 'everpad-list-ordered']),

            # Don't include 'checkbox' since it looks bad in some default themes
            (check_action, ['everpad-checkbox'], True),
            (table_action, ['insert-table', 'everpad-insert-table'], True),
            (link_action, ['insert-link'], True),
            (image_action, ['insert-image'], True),
            ]

        return map(lambda action: self._action_with_icon(*action), actions)

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

    def in_content(self, res):
        return self.page.mainFrame().evaluateJavaScript(
            'resExist("%s");' % (
                res.hash,
            ),
        )

    def _enable_text_direction_support(self):
        def is_rtl_language(language_code):
            rtl_languages = ['ar', 'fa', 'he', 'ur']
            for lang in rtl_languages:
                if language_code.startswith(lang):
                    return True
            return False

        import locale
        default_language = locale.getdefaultlocale()[0]
        if is_rtl_language(default_language):
            return True
        # If the default language is not a RTL language, go through the preferred list
        # of languages to see if one of them is RTL. Unfortunately, this is platform-specific
        # logic, and I couldn't find a portable way of doing it.
        preferred_languages = os.getenv('LANGUAGE', '').split(':')
        for language in preferred_languages:
            if is_rtl_language(language):
                return True

        return False

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


class ResourceItem(QWidget):
    def __init__(self, res):
        QWidget.__init__(self)
        self.res = res
        layout = QVBoxLayout()
        self.setLayout(layout)
        preview = QLabel()
        if 'image' in res.mime:
            pixmap = QPixmap(res.file_path).scaledToWidth(32)
            
        else:
            info = QFileInfo(res.file_path)
            pixmap = QFileIconProvider().icon(info).pixmap(32, 32)
        preview.setPixmap(pixmap)
        preview.setMask(pixmap.mask())
        preview.setMaximumHeight(32)
        label = QLabel()
        label.setText(res.file_name)
        layout.addWidget(preview)
        layout.addWidget(label)
        layout.setAlignment(Qt.AlignHCenter)
        self.setFixedWidth(64)
        self.setFixedHeight(64)


class ResourceEdit(object):  # TODO: move event to item
    """Abstraction for notebook edit"""

    def __init__(self, parent, app, widget, label, on_change):
        """Init and connect signals"""
        self.label = label
        self.parent = parent
        self.app = app
        self.widget = widget
        self.note = None
        self.on_change = on_change
        self._resource_labels = {}
        self._resources = []
        self._res_hash = {}
        self.widget.setLayout(QHBoxLayout())
        self.widget.layout().setAlignment(Qt.AlignLeft)
        self.mime = magic.open(magic.MIME_TYPE)
        self.mime.load()
        if int(self.app.settings.value(
            'note-resources-%d' % self.parent.note.id, 0,
        )):
            self.widget.show()
        self.label.linkActivated.connect(self.label_uri)
        self.label.setContextMenuPolicy(Qt.NoContextMenu)

    def update_label(self):
        self.label.setText(
            self.app.tr(
                '%d attached files: <a href="show">%s</a> / <a href="add">add another</a>',
            ) % (
                len(self._resources), self.app.tr('show') if self.widget.isHidden()
                else self.app.tr('hide'),
            ),
        )

    @Slot(QUrl)
    def label_uri(self, uri):
        uri = str(uri)
        if  uri == 'add':
            self.add()
        elif uri == 'show':
            if self.widget.isHidden():
                self.widget.show()
                visible = 1
            else:
                self.widget.hide()
                visible = 0
            self.app.settings.setValue(
                'note-resources-%d' % self.parent.note.id, visible,
            )
            self.update_label()

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
        self.update_label()

    def _put(self, res):
        """Put resource on widget"""
        item = ResourceItem(res)
        item.mouseReleaseEvent = partial(self.click, res)
        self.widget.layout().addWidget(item)
        self._resource_labels[res] = item
        self._res_hash[res.hash] = res
        res.in_content = False
        self.update_label()

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
            if not self.parent.note_edit.in_content(res):
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
        return res


class Editor(QMainWindow):  # TODO: kill this god shit
    """Note editor"""

    def __init__(self, app, note, *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        self.app = app
        self.note = note
        self.closed = False
        self.ui = Ui_Editor()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.init_controls()
        self.load_note(note)
        self.update_title()
        self.mark_untouched()
        geometry = self.app.settings.value("note-geometry-%d" % self.note.id)
        if not geometry:
            geometry = self.app.settings.value("note-geometry-default")
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
            self, self.app, self.ui.resourceArea, 
            self.ui.resourceLabel, self.mark_touched,
        )
        self.findbar = FindBar(self)
        self.init_toolbar()
        self.init_shortcuts()

    def init_shortcuts(self):
        self.save_btn.setShortcut(QKeySequence('Ctrl+s'))
        self.close_btn.setShortcut(QKeySequence('Ctrl+q'))

    def init_toolbar(self):
        self.save_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('document-save'), 
            self.tr('Save'), self.save,
        )
        self.close_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('window-close'), 
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
        self.find_action = QAction(QIcon.fromTheme('edit-find'),
                                   self.app.tr('Find'), self)
        self.find_action.setCheckable(True)
        self.find_action.triggered.connect(self.findbar.toggle_visible)
        self.ui.toolBar.addAction(self.find_action)
        self.ui.toolBar.addSeparator()
        self.pin = self.ui.toolBar.addAction(
            QIcon.fromTheme('edit-pin', QIcon.fromTheme('everpad-pin')),
            self.tr('Pin note'), self.mark_touched,
        )
        self.pin.setCheckable(True)
        self.pin.setChecked(self.note.pinnded)

    def load_note(self, note):
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
        self.note.pinnded = self.pin.isChecked()

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
        self.app.settings.setValue(
            "note-geometry-default", self.saveGeometry(),
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
