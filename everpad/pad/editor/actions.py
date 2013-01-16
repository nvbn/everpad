from PySide.QtGui import QIcon, QDialog, QWidget, QApplication
from PySide.QtCore import Slot
from PySide.QtWebKit import QWebPage
from everpad.interface.tableinsert import Ui_TableInsertDialog
from everpad.interface.image import Ui_ImageDialog
from everpad.interface.findbar import Ui_FindBar
from everpad.pad.tools import get_icon


class ImagePrefs(QDialog):
    def __init__(self, res, *args, **kwargs):
        QDialog.__init__(self, *args, **kwargs)
        self.app = QApplication.instance()
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


class TableWidget(QDialog):
    def __init__(self, parent, rows=None, cells=None, *args, **kwargs):
        QDialog.__init__(self, parent, *args, **kwargs)
        self.ui = Ui_TableInsertDialog()
        self.ui.setupUi(self)
        self.setWindowIcon(get_icon())
        if rows:  # typecasting sucks
            self.ui.rows.setText(str(int(rows)))
        if cells:
            self.ui.columns.setText(str(int(cells)))

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
