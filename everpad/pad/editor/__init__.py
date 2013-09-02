from PySide.QtGui import (
    QMainWindow, QIcon, QMessageBox, QAction,
    QShortcut, QKeySequence, QApplication,
)
from PySide.QtCore import Slot
from everpad.interface.editor import Ui_Editor
from everpad.pad.tools import get_icon
from everpad.pad.editor.actions import FindBar
from everpad.pad.editor.content import ContentEdit
from everpad.pad.editor.resources import ResourceEdit
from everpad.pad.editor.widgets import TagEdit, NotebookEdit
from everpad.pad.share_note import ShareNoteDialog
from everpad.basetypes import Resource, Note
from dbus.exceptions import DBusException
import dbus
import logging
import os


class Editor(QMainWindow):  # TODO: kill this god shit
    """Note editor"""

    def __init__(self, note, *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        # Configure logger.
        self.logger = logging.getLogger('everpad-editor')
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(
            os.path.expanduser('~/.everpad/logs/everpad.log'))
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.app = QApplication.instance()
        self.note = note
        self.closed = False
        self.ui = Ui_Editor()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.alternatives_template =\
            self.ui.alternativeVersions.text()
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
            self, self.ui.contentView, self.text_changed,
        )
        self.tag_edit = TagEdit(
            self, self.ui.tags, self.mark_touched,
        )
        self.notebook_edit = NotebookEdit(
            self, self.ui.notebook, self.mark_touched,
        )
        self.resource_edit = ResourceEdit(
            self, self.ui.resourceArea,
            self.ui.resourceLabel, self.mark_touched,
        )
        self.findbar = FindBar(self)
        self.init_toolbar()
        self.init_shortcuts()
        self.init_alternatives()
        self.app.data_changed.connect(self.init_alternatives)

    def init_alternatives(self):
        try:
            conflict_items = self.app.provider.get_note_alternatives(self.note.id)
            if conflict_items:
                conflicts = map(
                    lambda item: Note.from_tuple(self.app.provider.get_note(
                        item,
                    )), self.note.conflict_items,
                )
                text = self.alternatives_template % ', '.join(map(
                    lambda note: u'<a href="%d">%s</a>' % (
                        note.id, note.title,
                    ), conflicts,
                ))
                self.ui.alternativeVersions.setText(text)
                self.ui.alternativeVersions.linkActivated.connect(
                    lambda id: self.app.indicator.open(
                        Note.from_tuple(self.app.provider.get_note(int(id))),
                    )
                )
            else:
                self.ui.alternativeVersions.hide()
        except DBusException:
            self.ui.alternativeVersions.hide()

    def init_shortcuts(self):
        self.save_btn.setShortcut(QKeySequence('Ctrl+s'))
        self.close_btn.setShortcut(QKeySequence('Ctrl+q'))
        self.email_btn.setShortcut(QKeySequence('Ctrl+Shift+e'))
        self.print_btn.setShortcut(QKeySequence(self.tr('Ctrl+p')))
        QShortcut(QKeySequence(self.tr('Ctrl+w')), self, self.save_and_close)

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
        self.print_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('document-print'),
            self.tr('Print note'),
            self.note_edit.print_,
        )
        self.email_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('mail-unread'),
            self.tr('Email note'),
            self.note_edit.email_note,
        )
        self.email_btn = self.ui.toolBar.addAction(
            QIcon.fromTheme('emblem-shared'),
            self.tr('Share note'),
            self.share_note,
        )
        self.ui.toolBar.addSeparator()
        for action in self.note_edit.get_format_actions():
            self.ui.toolBar.addAction(action)
        self.ui.toolBar.addSeparator()
        self.find_action = QAction(QIcon.fromTheme('edit-find'),
                                   self.tr('Find'), self)
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
        self.logger.debug('Loading note: "%s"' % note.title)
        self.resource_edit.resources = map(Resource.from_tuple,
            self.app.provider.get_note_resources(note.id),
        )
        self.notebook_edit.notebook = note.notebook
        self.note_edit.title = note.title
        self.logger.debug('Note content: "%s"' % note.content)
        self.note_edit.content = note.content
        self.tag_edit.tags = note.tags

    def update_note(self):
        self.logger.debug('Updating note: "%s"' % self.note_edit.title)
        self.note.notebook = self.notebook_edit.notebook
        self.note.title = self.note_edit.title
        self.note.content = self.note_edit.content
        self.note.tags = dbus.Array(self.tag_edit.tags, signature='s')
        self.note.pinnded = self.pin.isChecked()

    def closeEvent(self, event):
        event.ignore()
        self.save_and_close()

    def text_changed(self):
        self.update_title()
        self.mark_touched()

    def update_title(self):
        title = self.note_edit.title
        if self.note.conflict_parent:
            title += self.tr(' alternative of: %s') % (
                Note.from_tuple(self.app.provider.get_note(
                    self.note.conflict_parent,
                )).title,
            )
        self.setWindowTitle(self.tr('Everpad / %s') % title)

    @Slot()
    def save(self):
        self.logger.debug('Saving note: "%s"' % self.note.title)
        self.mark_untouched()
        self.update_note()
        self.app.provider.update_note(self.note.struct)
        self.app.provider.update_note_resources(
            self.note.id, dbus.Array(map(lambda res:
                res.struct, self.resource_edit.resources,
            ), signature=Resource.signature),
        )
        self.app.send_notify(self.tr('Note "%s" saved!') % self.note.title)

    @Slot()
    def save_and_close(self):
        if self.touched:
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
            self.app.send_notify(self.tr('Note "%s" deleted!') % self.note.title)
            self.close()

    @Slot()
    def close(self):
        msg = QMessageBox(
            QMessageBox.Critical,
            self.tr("Close without Saving"),
            self.tr("Are you sure want to close this note without saving?"),
            QMessageBox.Yes | QMessageBox.No
        )
        if not self.touched or msg.exec_() == QMessageBox.Yes:
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

    def share_note(self):
        dialog = ShareNoteDialog(self.note, parent=self)
        dialog.exec_()
