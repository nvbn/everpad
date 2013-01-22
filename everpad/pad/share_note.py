import sys
sys.path.append('../..')
from PySide.QtGui import QDialog, QApplication
from everpad.basetypes import Note
from everpad.interface.share_note import Ui_ShareNote
from everpad.pad.tools import get_icon


class ShareNoteDialog(QDialog):
    """Share note dialog"""

    def __init__(self, note, *args, **kwargs):
        """init dialog and connect signals"""
        QDialog.__init__(self, *args, **kwargs)
        self.app = QApplication.instance()
        self.canceled = False
        self.ui = Ui_ShareNote()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        self.note = Note.from_tuple(
            self.app.provider.get_note(note.id),
        )
        self.app.data_changed.connect(self.data_changed)
        self.ui.cancelButton.clicked.connect(self.cancel)
        self.ui.copyButton.clicked.connect(self.copy_url)
        if not self.note.share_url:
            self.start_sharing()
        self.update()

    def start_sharing(self):
        """Start sharing note"""
        self.app.provider.share_note(self.note.id)

    def copy_url(self):
        """Copy sharing url"""
        url = self.ui.shareLink.text()
        self.app.clipboard().setText(url)

    def cancel(self):
        """Cancel sharing note"""
        self.canceled = True
        self.app.provider.stop_sharing_note(self.note.id)
        self.update()

    def data_changed(self):
        """On data changed slot"""
        self.note = Note.from_tuple(
            self.app.provider.get_note(self.note.id),
        )
        self.update()

    def update(self):
        """Update dialog behavior"""
        self.update_title()
        if self.canceled:
            self.render_canceled()
        elif self.note.share_url:
            self.render_shared()
        else:
            self.render_wait()

    def update_title(self):
        """Update dialog title"""
        self.setWindowTitle(self.tr(
            'Everpad / sharing "%s"' % self.note.title,
        ))

    def render_shared(self):
        """Render for already shared note"""
        self.ui.waitText.hide()
        self.ui.sharedWidget.show()
        self.ui.shareLink.setText(self.note.share_url)

    def render_canceled(self):
        """Render for canceled sharing"""
        self.ui.waitText.show()
        self.ui.sharedWidget.hide()
        self.ui.waitText.setText(self.tr('Note sharing canceled'))

    def render_wait(self):
        """Render for wait sharing"""
        self.ui.waitText.show()
        self.ui.sharedWidget.hide()
        self.ui.waitText.setText(self.tr('Sharing in proccess...'))
