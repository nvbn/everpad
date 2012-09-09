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
from everpad.interface.notebook import Ui_Notebook
from everpad.pad.tools import get_icon
from everpad.tools import get_provider, get_auth_token
from everpad.basetypes import Note, Notebook, Resource
from everpad.const import CONSUMER_KEY, CONSUMER_SECRET, HOST
from everpad import monkey
from functools import partial
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
            self.ui.syncDelayBox.addItem('%d minutes' % delay,
                userData=str(delay * 60 * 1000),
            )
        self.ui.syncDelayBox.addItem('One hour', userData='3600000')
        self.ui.syncDelayBox.addItem('Manual', userData='-1')
        active_index = self.ui.syncDelayBox.findData(str(
            self.app.provider.get_sync_delay(),
        ))
        self.ui.syncDelayBox.setCurrentIndex(active_index)
        self.ui.syncDelayBox.currentIndexChanged.connect(self.delay_changed)
        self.ui.tabWidget.currentChanged.connect(self.update_tabs)
        self.ui.createNotebook.clicked.connect(self.create_notebook)
        self.ui.authBtn.clicked.connect(self.change_auth)
        self.ui.autoStart.stateChanged.connect(self.auto_start_state)
        self.update_tabs()

    @Slot()
    def update_tabs(self):
        if get_auth_token():
            self.ui.authBtn.setText('Remove Authorisation')
            self.ui.notebookTab.setEnabled(True)
            self.init_notebooks()
        else:
            self.ui.authBtn.setText('Authorise')
            self.ui.notebookTab.setEnabled(False)
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

    def init_notebooks(self):
        frame = QFrame()
        layout = QVBoxLayout()
        frame.setLayout(layout)
        self.ui.scrollArea.setWidget(frame)
        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            count = self.app.provider.get_notebook_notes_count(notebook.id)
            widget = QWidget()
            menu = QMenu(self)
            menu.addAction(self.tr('Change Name'), Slot()(partial(
                self.change_notebook, notebook=notebook,
            )))
            action = menu.addAction(self.tr('Remove Notebook'), Slot()(partial(
                self.remove_notebook, notebook=notebook,
            )))
            action.setEnabled(False)
            widget.ui = Ui_Notebook()
            widget.ui.setupUi(widget)
            widget.ui.name.setText(notebook.name)
            widget.ui.content.setText(self.tr('Containts %d notes') % count)
            widget.ui.actionBtn.setIcon(QIcon.fromTheme('gtk-properties'))
            widget.setFixedHeight(50)
            layout.addWidget(widget)
            widget.ui.actionBtn.clicked.connect(Slot()(partial(
                self.show_notebook_menu,
                menu=menu, widget=widget,
            )))

    def show_notebook_menu(self, menu, widget):
        pos = widget.mapToGlobal(widget.ui.actionBtn.pos())
        pos.setY(pos.y() + widget.ui.actionBtn.geometry().height() / 2)
        pos.setX(pos.x() + widget.ui.actionBtn.geometry().width() / 2)
        menu.exec_(pos)

    def remove_notebook(self, notebook):
        msg = QMessageBox(
            QMessageBox.Critical,
            self.tr("You try to delete a notebook"),
            self.tr("Are you sure want to delete this notebook and notes in it?"),
            QMessageBox.Yes | QMessageBox.No
        )
        ret = msg.exec_()
        if ret == QMessageBox.Yes:
            self.app.provider.delete_notebook(notebook.id)
            self.app.send_notify(u'Notebook "%s" deleted!' % notebook.name)
            self.update_tabs()

    def change_notebook(self, notebook):
        name, status = self._notebook_new_name(
            self.tr('Change notebook name'), notebook.name,
        )
        if status:
            notebook.name = name
            self.app.provider.update_notebook(notebook.struct)
            self.app.send_notify(u'Notebook "%s" renamed!' % notebook.name)
            self.update_tabs()

    @Slot()
    def create_notebook(self):
        name, status = self._notebook_new_name(
            self.tr('Create new notebook'),
        )
        if status:
            self.app.provider.create_notebook(name)
            self.app.send_notify(u'Notebook "%s" created!' % name)
            self.update_tabs()

    def _notebook_new_name(self, title, exclude=''):
        names = map(lambda nb: Notebook.from_tuple(nb).name,
            self.app.provider.list_notebooks(),
        )
        try:
            names.remove(exclude)
        except ValueError:
            pass
        name, status = QInputDialog.getText(self, title,
            self.tr('Enter notebook name:'),
        )
        while name in names and status:
            name, status = QInputDialog.getText(self, title,
                self.tr('Notebook with this name already exist. Enter notebook name'),
            )
        return name, status

    def closeEvent(self, event):
        event.ignore()
        self.closed = True
        self.hide()
