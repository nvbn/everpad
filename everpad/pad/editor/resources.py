from PySide.QtGui import (
    QPixmap, QLabel, QVBoxLayout, QFileDialog,
    QMenu, QInputDialog, QFileIconProvider,
    QWidget, QHBoxLayout, QApplication,
)
from PySide.QtCore import Slot, Qt, QUrl, QFileInfo
from everpad.basetypes import Resource, NONE_ID
from everpad.tools import prepare_file_path
from functools import partial
import subprocess
import magic
import os
import shutil
import hashlib
import urllib


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

    def __init__(self, parent, widget, label, on_change):
        """Init and connect signals"""
        self.label = label
        self.parent = parent
        self.app = QApplication.instance()
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
            self.app.translate('ResourceEdit', '%d attached files: <a href="show">%s</a> / <a href="add">%s</a>'
            ) % (
                len(self._resources), self.app.translate('ResourceEdit', 'show') if self.widget.isHidden()
                else self.app.translate('ResourceEdit', 'hide'),
                self.app.translate('ResourceEdit', 'add another'),
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
            menu.addAction(
                self.app.translate('ResourceEdit', 'Put to Content'), Slot()(partial(
                    self.to_content, res=res,
                )),
            )
            if not self.parent.note_edit.in_content(res):
                menu.addAction(
                    self.app.translate('ResourceEdit', 'Remove Resource'), Slot()(partial(
                        self.remove, res=res,
                    ))
                )
            menu.addAction(
                self.app.translate('ResourceEdit', 'Save As'), Slot()(partial(
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
            self.app.translate("ResourceEdit", "Delete Resource"),
            self.app.translate("ResourceEdit", "Are you sure want to delete this resource?"),
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
        file_path = prepare_file_path(dest, file_name)
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
