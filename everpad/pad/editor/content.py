from PySide.QtGui import (
    QIcon, QAction, QFileDialog,
    QShortcut, QKeySequence, QInputDialog,
    QPrintPreviewDialog, QPrinter, QDropEvent,
    QDragEnterEvent, QDragMoveEvent, QApplication,
    QDesktopServices,
)
from PySide.QtCore import (
    Slot, Qt, QPoint, QObject, Signal, QUrl,
    QMimeData,
)
from PySide.QtWebKit import QWebPage, QWebSettings
from everpad.basetypes import Note
from everpad.pad.editor.actions import ImagePrefs, TableWidget
from everpad.pad.tools import file_icon_path
from everpad.tools import sanitize, clean, html_unescape, resource_filename
from everpad.const import DEFAULT_FONT, DEFAULT_FONT_SIZE
from BeautifulSoup import BeautifulSoup, Tag
from functools import partial
from copy import copy
import webbrowser
import os
import json
import re
import cgi


url = re.compile(r"((https?://|www)[-\w./#?%=&]+)")


def set_links(text):
    """Insert a href"""
    soup = BeautifulSoup(text)
    # don't change if text contains html
    if len(soup.findAll()):
        return text
    else:
        return url.sub(r'<a href="\1">\1</a>', text)


class Page(QWebPage):
    def __init__(self, edit):
        QWebPage.__init__(self)
        self.current = None
        self.edit = edit
        self.active_image = None
        self.active_link = None
        self.active_table = None
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
        QWebSettings.globalSettings().setAttribute(
            QWebSettings.DeveloperExtrasEnabled, True,
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

    @Slot(str)
    def set_active_table(self, id):
        self.active_table = id

    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        print lineNumber, ':', message

    def acceptNavigationRequest(self, frame, request, type):
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier and type == QWebPage.NavigationTypeLinkClicked:
            QDesktopServices.openUrl(request.url())
        return False

    def event(self, e):
        if isinstance(e, QDragEnterEvent):
            data = e.mimeData()
            if data.hasUrls():
                e.accept()
            else:
                e.ignore()
            return True
        elif isinstance(e, QDragMoveEvent):
            pass
        elif isinstance(e, QDropEvent):
            self.edit.insert_files(e.mimeData().urls(), e.pos())
            return True

        return super(Page, self).event(e)


class ContentEdit(QObject):
    _editor_path = os.path.join(
        os.path.dirname(__file__), 'editor.html',
    )
    if not os.path.exists(_editor_path):
        _editor_path = resource_filename('share/everpad/editor.html')

    _html = open(_editor_path).read()

    copy_available = Signal(bool)

    def __init__(self, parent, widget, on_change):
        QObject.__init__(self)
        self.parent = parent
        self.app = QApplication.instance()
        self.widget = widget
        self.page = Page(self)
        self._on_change = on_change
        self._title = None
        self._content = None
        self._hovered_url = None
        self.widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.widget.customContextMenuRequested.connect(self.context_menu)
        self._init_actions()
        self._init_shortcuts()
        self._last_table_num = 0

    def _init_actions(self):
        self.check_action = QAction(self.tr('Insert Checkbox'), self)
        self.check_action.triggered.connect(self._insert_check)
        self.link_action = QAction(self.tr('Insert Link'), self)
        self.link_action.triggered.connect(self._insert_link)
        self.table_action = QAction(self.tr('Insert Table'), self)
        self.table_action.triggered.connect(self._insert_table)
        self.image_action = QAction(self.tr('Insert Image'), self)
        self.image_action.triggered.connect(self._insert_image)
        self.change_link = QAction(self.tr('Change link'), self)
        self.change_link.triggered.connect(
            Slot()(partial(self._change_link, self.page.active_link))
        )
        self.remove_link = QAction(self.tr('Remove link'), self)
        self.remove_link.triggered.connect(self._remove_link)

    def _init_shortcuts(self):
        for key, action in (
            ('Ctrl+b', QWebPage.ToggleBold),
            ('Ctrl+i', QWebPage.ToggleItalic),
            ('Ctrl+u', QWebPage.ToggleUnderline),
            ('Ctrl+Shift+b', QWebPage.InsertUnorderedList),
            ('Ctrl+Shift+o', QWebPage.InsertOrderedList),
            ('Ctrl+Shift+v', QWebPage.PasteAndMatchStyle),
            ('Ctrl+k', self.link_action),
            ('Ctrl+Shift+k',  self.change_link),
            ('Ctrl+l',  QWebPage.AlignLeft),
            ('Ctrl+r',  QWebPage.AlignRight),
            ('Ctrl+e',  QWebPage.AlignCenter),
            ('Ctrl+j',  QWebPage.AlignJustified),
            ('Ctrl+t',  QWebPage.ToggleStrikethrough),
            ('Ctrl+Space', QWebPage.RemoveFormat),
            ('Ctrl+Shift+c', self.check_action),
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
                del media['title']
        # remove tables id's before save
        for table in soup.findAll('table'):
            del table['id']
        self._content = sanitize(
            soup=soup.find(id='content'),
        ).replace('  ', u'\xa0\xa0').replace(u'\xa0 ', u'\xa0\xa0')
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
                    if media['type'].find('image') == 0:
                        media['src'] = 'file://%s' % res.file_path
                    else:
                        media['src'] = file_icon_path
                    media['title'] = res.file_name
                    res.in_content = True
                    # wrap in link to make clickable
                    tag = Tag(soup, "a", [("href", 'file://%s' % res.file_path)])
                    media.replaceWith(tag)
                    tag.insert(0, media)
                else:
                    media['src'] = ''
                    media['title'] = ''
            else:
                media.hidden = True
        # set tables id's for identifing on hover
        for num, table in enumerate(soup.findAll('table')):
            table['id'] = 'table_%d' % num
            self._last_table_num = num
        self._content = re.sub(
            r'(&nbsp;| ){5}', '<img class="tab" />',
            unicode(soup).replace(u'\xa0', ' '),
        )  # shit!
        self.apply()

    def apply(self):
        """Apply title and content when filled"""
        if None not in (self._title, self._content):
            html = self._html.replace(
                '{{ title }}', cgi.escape(self._title),
            ).replace(
                '{{ content }}', self._content,
            )
            self.page.mainFrame().setHtml(html)
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
        if url.scheme() == 'evernote':
            note_guid = url.toString().split('/')[6]
            note = Note.from_tuple(
                self.app.provider.get_note_by_guid(note_guid),
            )
            self.app.open(note)
        else:
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
        paste_wo.setText(self.tr('Paste as Plain Text'))
        menu.addAction(paste_wo)
        if self._hovered_url:
            menu.addAction(self.page.action(QWebPage.CopyLinkToClipboard))
            menu.addAction(self.change_link)
            menu.addAction(self.remove_link)
            self.page.active_link = None
        if self.page.active_image:
            res = self.parent.resource_edit.get_by_hash(self.page.active_image)
            self.page.active_image = None
            menu.addAction(
                self.tr('Image Preferences'),
                Slot()(partial(self._show_image_dialog, res)),
            )
        if self.page.active_table:
            menu.addAction(
                self.tr('Change table'),
                Slot()(partial(self._update_table, self.page.active_table)),
            )
            self.page.active_table = None
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
            if isinstance(action, QWebPage.WebAction):
                action = self.page.action(action)
            action.trigger()

    @Slot()
    def _insert_link(self):
        url, ok = QInputDialog.getText(self.parent,
            self.tr('Everpad / Insert link'),
            self.tr('Press link address'),
        )
        if ok and url:
            self.page.mainFrame().evaluateJavaScript(
                'insertLink(%s);' % json.dumps(url),
            )
            self.page_changed()

    def _change_link(self, url):
        url, ok = QInputDialog.getText(self.parent,
            self.tr('Everpad / Change link'),
            self.tr('Press new link address'),
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
        dialog = TableWidget(self.parent)
        self._last_table_num += 1
        if dialog.exec_():
            self.page.mainFrame().evaluateJavaScript(
                'insertTable(%s, %s, "%s", "table_%d");' % (
                    dialog.ui.rows.text(),
                    dialog.ui.columns.text(),
                    dialog.get_width(),
                    self._last_table_num,
                )
            )

    def _update_table(self, id):
        rows = self.page.mainFrame().evaluateJavaScript(
            'getTableRows("%s")' % id,
        )
        cells = self.page.mainFrame().evaluateJavaScript(
            'getTableCells("%s")' % id,
        )
        dialog = TableWidget(self.parent, rows, cells)
        self._last_table_num += 1
        if dialog.exec_():
            self.page.mainFrame().evaluateJavaScript(
                'updateTable(%s, %s, "%s", "%s");' % (
                    dialog.ui.rows.text(),
                    dialog.ui.columns.text(),
                    dialog.get_width(),
                    id,
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
            filter=self.tr("Image Files (*.png *.jpg *.bmp *.gif)"),
        )[0]
        if name:
            self._insert_image_from_path(name)

    def _insert_image_from_path(self, path):
            res = self.parent.resource_edit.add_attach(path)
            self.paste_res(res)

    def get_format_actions(self):
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
            (self.check_action, ['everpad-checkbox'], True),
            (self.table_action, ['insert-table', 'everpad-insert-table'], True),
            (self.link_action, ['insert-link'], True),
            (self.image_action, ['insert-image'], True),
        ]
        return map(lambda action: self._action_with_icon(*action), actions)

    def paste_res(self, res):
        if res.mime.find('image') == 0:
            preview = 'file://%s' % res.file_path
        else:
            preview = file_icon_path
        self.page.mainFrame().evaluateJavaScript(
            'insertRes("%s", "%s", "%s");' % (
                preview, res.hash, res.mime,
            ),
        )
        self.page_changed()

    def _show_image_dialog(self, res):
        res.w = int(self.page.active_width)
        res.h = int(self.page.active_height)
        dialog = ImagePrefs(res, self.parent)
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
            if not language_code:
                return False
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

    def print_(self):
        """Print note with preview"""
        printer = QPrinter()
        dialog = QPrintPreviewDialog(printer)
        dialog.paintRequested.connect(self.page.view().print_)
        dialog.exec_()

    def email_note(self):
        body = self.page.mainFrame().toPlainText()[
            len(self.title):
        ].strip()
        url = QUrl("mailto:")
        url.addQueryItem("subject", self.title)
        url.addQueryItem("body", body)
        QDesktopServices.openUrl(url)

    def insert_files(self, urls, pos):
        """Not only images"""
        image_extensions = ['.png', '.jpg', '.bmp', '.gif']
        for url in urls:
            if url.scheme() == 'file':
                path = url.path()
                ext = os.path.splitext(path)[1]
                if os.path.exists(path) and ext in image_extensions:
                    self._insert_image_from_path(path)
                else:
                    self.parent.resource_edit.add_attach(path)
