import sys
sys.path.append('../..')
from PySide.QtGui import (
    QDialog, QIcon, QPixmap,
    QLabel, QVBoxLayout, QFrame,
    QMessageBox, QAction, QWidget,
    QListWidgetItem, QMenu, QInputDialog,
)
from PySide.QtCore import Slot, Qt, QPoint
from everpad.interface.management import Ui_Dialog
from everpad.pad.tools import get_icon
from everpad.tools import get_provider, get_auth_token
from everpad.const import CONSUMER_KEY, CONSUMER_SECRET, HOST
from everpad import monkey
import urllib
import urlparse
import subprocess
import webbrowser
import oauth2 as oauth
import os
import shutil


class Management(QDialog):
    """Management dialog"""

    def __init__(self, app, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.app = app
        self.closed = False
        self.startup_path = os.path.expanduser('~/.config/autostart/')
        self.startup_file = os.path.join(self.startup_path, 'everpad.desktop')
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
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
        self.update_tabs()

    @Slot()
    def update_tabs(self):
        if get_auth_token():
            self.ui.authBtn.setText(self.tr('Remove Authorisation'))
        else:
            self.ui.authBtn.setText(self.tr('Authorise'))
        self.ui.autoStart.setCheckState(Qt.Checked
            if os.path.isfile(self.startup_file)
        else Qt.Unchecked)

    @Slot()
    def auto_start_state(self):
        if self.ui.autoStart.checkState() == Qt.Unchecked:
            try:
                os.unlink(self.startup_file)
            except OSError:
                pass
        else:
            print self.startup_file
            shutil.copyfile(
                '/usr/share/applications/everpad.desktop',
                self.startup_file,
            )

    @Slot(int)
    def delay_changed(self, index):
        self.app.provider.set_sync_delay(
            int(self.ui.syncDelayBox.itemData(index)),
        )

    @Slot()
    def change_auth(self):
        if get_auth_token():
            self.app.provider.remove_authentication()
        else:
            consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
            client = oauth.Client(consumer)
            resp, content = client.request(
                'https://%s/oauth?oauth_callback=' % HOST + urllib.quote('http://localhost:15216/'), 
            'GET')
            data = dict(urlparse.parse_qsl(content))
            url = 'https://%s/OAuth.action?oauth_token=' % HOST + urllib.quote(data['oauth_token'])
            webbrowser.open(url)
            os.system('killall everpad-web-auth')
            try:
                subprocess.Popen([
                    'everpad-web-auth', '--token', data['oauth_token'],
                    '--secret', data['oauth_token_secret'],
                ])
            except OSError:
                subprocess.Popen([
                    'python', '../auth.py', '--token',
                    data['oauth_token'], '--secret',
                    data['oauth_token_secret'],
                ])
        self.update_tabs()

    def closeEvent(self, event):
        event.ignore()
        self.closed = True
        self.hide()
