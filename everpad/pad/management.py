import sys
sys.path.append('../..')
from PySide.QtGui import QDialog, QFont, QApplication, QMessageBox, QCursor, QListWidgetItem, QMenu
from PySide.QtWebKit import QWebPage
from PySide.QtCore import Slot, Qt
from PySide.QtNetwork import QNetworkAccessManager, QSslConfiguration, QSsl
from everpad.interface.management import Ui_Dialog
from everpad.pad.tools import get_icon
from everpad.const import (
    CONSUMER_KEY, CONSUMER_SECRET, HOST,
    DEFAULT_FONT, DEFAULT_FONT_SIZE,
    DEFAULT_INDICATOR_LAYOUT,
)
from everpad import monkey
from everpad.tools import get_proxy_config, resource_filename
import urllib
import urlparse
import oauth2 as oauth
import os
import shutil
from httplib2 import ProxyInfo
from httplib2.socks import PROXY_TYPE_HTTP


def get_oauth_proxy(scheme):
    proxy = get_proxy_config(scheme)
    if proxy is None:
        return None
    proxy = urlparse.urlparse(proxy)
    return ProxyInfo(
        proxy_type=PROXY_TYPE_HTTP,
        proxy_host=proxy.hostname,
        proxy_port=proxy.port,
        proxy_user=proxy.username or None,
        proxy_pass=proxy.password or None,
    )


class TLSNetworkAccessManager(QNetworkAccessManager):
    def createRequest(self, op, request, outgoingData=None):
        conf = QSslConfiguration()
        conf.setProtocol(QSsl.TlsV1)
        request.setSslConfiguration(conf)
        return QNetworkAccessManager.createRequest(self, op, request, outgoingData)


class AuthPage(QWebPage):
    def __init__(self, token, secret, parent, *args, **kwargs):
        QWebPage.__init__(self, *args, **kwargs)
        self.token = token
        self.secret = secret
        self.parent = parent
        manager = TLSNetworkAccessManager(self)
        manager.sslErrors.connect(self.ssl)
        self.setNetworkAccessManager(manager)

    def acceptNavigationRequest(self, frame, request, type):
        url = request.url()
        if 'everpad' in url.host():
            verifier = url.queryItemValue('oauth_verifier')
            token = oauth.Token(self.token, self.secret)
            token.set_verifier(verifier)
            consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
            client = oauth.Client(consumer, token,
                                  proxy_info=get_oauth_proxy('https'))
            resp, content = client.request('https://%s/oauth' % HOST, 'POST')
            access_token = dict(urlparse.parse_qsl(content))
            self.parent.auth_finished(access_token['oauth_token'])
        return True

    def ssl(self, reply, errors):
        reply.ignoreSslErrors()


class Management(QDialog):
    """Management dialog"""

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.app = QApplication.instance()
        self.closed = False
        self.startup_path = os.path.expanduser('~/.config/autostart/')
        if not os.path.exists(self.startup_path):
            os.makedirs(self.startup_path)
        self.startup_file = os.path.join(self.startup_path, 'everpad.desktop')
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.ui.webView.hide()
        self.setWindowIcon(get_icon())
        for delay in (5, 10, 15, 30):
            self.ui.syncDelayBox.addItem(self.tr('%d minutes') % delay,
                userData=str(delay * 60 * 1000),
            )
        self.ui.syncDelayBox.addItem(self.tr('One hour'), userData='3600000')
        self.ui.syncDelayBox.addItem(self.tr('Manual'), userData='-1')
        active_index = self.ui.syncDelayBox.findData(str(
            self.app.provider.get_sync_delay(),
        ))
        self.ui.syncDelayBox.setCurrentIndex(active_index)
        self.ui.syncDelayBox.currentIndexChanged.connect(self.delay_changed)
        self.ui.tabWidget.currentChanged.connect(self.update_tabs)
        self.ui.authBtn.clicked.connect(self.change_auth)
        self.ui.autoStart.stateChanged.connect(self.auto_start_state)
        self.ui.noteFont.currentFontChanged.connect(self.font_changed)
        self.ui.noteSize.valueChanged.connect(self.font_size_changed)
        self.ui.blackTray.stateChanged.connect(self.tray_changed)
        self.ui.progressCheckBox.stateChanged.connect(self.progress_changed)
        self.layout_list = self.ui.listWidget_indLayout
        self.layout_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.layout_list.customContextMenuRequested.connect(self.layout_list_contextMenu)
        layout_list_model = self.layout_list.model()
        layout_list_model.layoutChanged.connect(self.save_layout_list)
        self.layout_labels = {
            'create_note': self.tr('Create Note'),
            'pin_notes' : self.tr('Pinned Notes'),
            'all_notes' : self.tr('All Notes'),
            'notes'     : self.tr('Notes'),
            'sync'      : self.tr('Last Sync'),
            }
        self.load_layout_list(self.app.settings.value('menu-order', DEFAULT_INDICATOR_LAYOUT))
        self.ui.searchOnHome.stateChanged.connect(self.search_on_home_changed)
        self.ui.sortByNotebook.stateChanged.connect(self.sort_by_notebook_changed)
        self.ui.buttonBox.clicked.connect(self.close_clicked)
        self.update_tabs()

    def on_default_layout(self):
        self.load_layout_list(DEFAULT_INDICATOR_LAYOUT)
        self.save_layout_list()

    def load_layout_list(self, settings):
        self.layout_list.clear()
        for menu_item in settings:
            font = QFont()
            if menu_item == 'pin_notes' or menu_item == 'notes':
                font.setStyle(QFont.StyleItalic)
            else:
                font.setWeight(QFont.DemiBold)
            item = QListWidgetItem(self.layout_labels[menu_item])
            item.setData(Qt.UserRole, menu_item)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFont(font)
            self.layout_list.addItem(item)

    def layout_list_contextMenu(self, pos):
        menu = QMenu()
        default_action = menu.addAction(self.tr("Reset Layout"))
        default_action.triggered.connect(self.on_default_layout)
        menu.exec_(QCursor.pos())

    def save_layout_list(self):
        all_items = self.layout_list.findItems('*', Qt.MatchWildcard)
        user_settings = []
        for item in all_items:
            user_settings.append(item.data(Qt.UserRole))
        self.app.settings.setValue('menu-order', user_settings)

    @Slot(str)
    def font_size_changed(self, size):
        self.app.settings.setValue('note-font-size', size)

    @Slot(QFont)
    def font_changed(self, font):
        self.app.settings.setValue('note-font-family', font.family())

    @Slot()
    def tray_changed(self):
        if self.ui.blackTray.checkState() == Qt.Unchecked:
            self.app.settings.setValue('black-icon', 0)
        else:
            self.app.settings.setValue('black-icon', 1)
        self.app.update_icon()

    @Slot()
    def progress_changed(self):
        if self.ui.progressCheckBox.checkState() == Qt.Unchecked:
            self.app.settings.setValue('launcher-progress', 0)
        else:
            self.app.settings.setValue('launcher-progress', 1)

    @Slot()
    def search_on_home_changed(self):
        if self.ui.searchOnHome.checkState() == Qt.Unchecked:
            value = '0'
        else:
            value = '1'
        self.app.provider.set_settings_value('search-on-home', value)

    @Slot()
    def sort_by_notebook_changed(self):
        value = ('0' if self.ui.sortByNotebook.checkState() == Qt.Unchecked 
                     else '1')
        self.app.provider.set_settings_value('sort-by-notebook', value)

    @Slot()
    def update_tabs(self):
        if self.app.provider.is_authenticated():
            self.ui.authBtn.setText(self.tr('Remove Authorisation'))
        else:
            self.ui.authBtn.setText(self.tr('Authorise'))
        self.ui.autoStart.setCheckState(Qt.Checked
            if os.path.isfile(self.startup_file)
        else Qt.Unchecked)
        self.ui.noteFont.setCurrentFont(QFont(self.app.settings.value(
            'note-font-family', DEFAULT_FONT,
        )))
        self.ui.noteSize.setValue(int(self.app.settings.value(
            'note-font-size', DEFAULT_FONT_SIZE,
        )))
        self.ui.blackTray.setCheckState(Qt.Checked
            if int(self.app.settings.value('black-icon', 0))
        else Qt.Unchecked)
        self.ui.progressCheckBox.setCheckState(Qt.Checked
            if int(self.app.settings.value('launcher-progress', 1))
        else Qt.Unchecked)
        self.ui.searchOnHome.setCheckState(Qt.Checked
            if int(self.app.provider.get_settings_value('search-on-home') or 1)
        else Qt.Unchecked)
        self.ui.sortByNotebook.setCheckState(Qt.Checked
            if int(self.app.provider.get_settings_value('sort-by-notebook') or 0)
        else Qt.Unchecked)

    @Slot()
    def auto_start_state(self):
        if self.ui.autoStart.checkState() == Qt.Unchecked:
            try:
                os.unlink(self.startup_file)
            except OSError:
                pass
        else:
            shutil.copyfile(
                resource_filename('share/applications/everpad.desktop'),
                self.startup_file,
            )

    @Slot(int)
    def delay_changed(self, index):
        self.app.provider.set_sync_delay(
            int(self.ui.syncDelayBox.itemData(index)),
        )

    @Slot()
    def change_auth(self):
        if self.app.provider.is_authenticated():
            msgBox = QMessageBox(
                QMessageBox.Critical,
                self.tr("You are trying to remove authorisation"),
                self.tr("""
                Are you sure want to remove authoristion?
                It remove all not synced changes!
                """.strip()),
                QMessageBox.Yes | QMessageBox.No
            )
            ret = msgBox.exec_()
            if ret == QMessageBox.Yes:
                self.app.provider.remove_authentication()
                self.update_tabs()
        else:
            self.ui.tabWidget.hide()
            self.ui.webView.show()
            consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
            client = oauth.Client(consumer, proxy_info=get_oauth_proxy('https'))
            resp, content = client.request(
                'https://%s/oauth?oauth_callback=' % HOST + urllib.quote('http://everpad/'),
            'GET')
            data = dict(urlparse.parse_qsl(content))
            url = 'http://%s/OAuth.action?oauth_token=' % HOST + urllib.quote(data['oauth_token'])
            page = AuthPage(
                data['oauth_token'], data['oauth_token_secret'], self,
            )
            self.ui.webView.setPage(page)
            page.mainFrame().load(url)

    @Slot()
    def close_clicked(self):
        self.close()

    def auth_finished(self, token):
        self.app.provider.authenticate(token)
        self.ui.webView.hide()
        self.ui.tabWidget.show()
        self.update_tabs()

    def closeEvent(self, event):
        event.ignore()
        self.closed = True
        self.hide()
