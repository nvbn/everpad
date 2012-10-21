# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'everpad/interface/findbar.ui'
#
# Created: Sun Oct 21 07:01:56 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_FindBar(object):
    def setupUi(self, FindBar):
        FindBar.setObjectName("FindBar")
        FindBar.resize(750, 33)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(FindBar.sizePolicy().hasHeightForWidth())
        FindBar.setSizePolicy(sizePolicy)
        self.horizontalLayout = QtGui.QHBoxLayout(FindBar)
        self.horizontalLayout.setContentsMargins(3, 3, 3, 3)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.btnClose = QtGui.QPushButton(FindBar)
        self.btnClose.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("../../../../.designer/backup"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.btnClose.setIcon(icon)
        self.btnClose.setObjectName("btnClose")
        self.horizontalLayout.addWidget(self.btnClose)
        self.lblFind = QtGui.QLabel(FindBar)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lblFind.sizePolicy().hasHeightForWidth())
        self.lblFind.setSizePolicy(sizePolicy)
        self.lblFind.setObjectName("lblFind")
        self.horizontalLayout.addWidget(self.lblFind)
        self.edtFindText = QtGui.QLineEdit(FindBar)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.edtFindText.sizePolicy().hasHeightForWidth())
        self.edtFindText.setSizePolicy(sizePolicy)
        self.edtFindText.setMinimumSize(QtCore.QSize(240, 0))
        self.edtFindText.setObjectName("edtFindText")
        self.horizontalLayout.addWidget(self.edtFindText)
        self.btnPrevious = QtGui.QPushButton(FindBar)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("../../../../../../.designer/backup"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.btnPrevious.setIcon(icon1)
        self.btnPrevious.setObjectName("btnPrevious")
        self.horizontalLayout.addWidget(self.btnPrevious)
        self.btnNext = QtGui.QPushButton(FindBar)
        self.btnNext.setIcon(icon1)
        self.btnNext.setObjectName("btnNext")
        self.horizontalLayout.addWidget(self.btnNext)
        self.btnHighlight = QtGui.QPushButton(FindBar)
        self.btnHighlight.setCheckable(True)
        self.btnHighlight.setObjectName("btnHighlight")
        self.horizontalLayout.addWidget(self.btnHighlight)
        self.chkMatchCase = QtGui.QCheckBox(FindBar)
        self.chkMatchCase.setObjectName("chkMatchCase")
        self.horizontalLayout.addWidget(self.chkMatchCase)
        spacerItem = QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)

        self.retranslateUi(FindBar)
        QtCore.QMetaObject.connectSlotsByName(FindBar)

    def retranslateUi(self, FindBar):
        FindBar.setWindowTitle(QtGui.QApplication.translate("FindBar", "Form", None, QtGui.QApplication.UnicodeUTF8))
        self.lblFind.setText(QtGui.QApplication.translate("FindBar", "Find:", None, QtGui.QApplication.UnicodeUTF8))
        self.btnPrevious.setText(QtGui.QApplication.translate("FindBar", "Previous", None, QtGui.QApplication.UnicodeUTF8))
        self.btnNext.setText(QtGui.QApplication.translate("FindBar", "Next", None, QtGui.QApplication.UnicodeUTF8))
        self.btnHighlight.setText(QtGui.QApplication.translate("FindBar", "Highlight All", None, QtGui.QApplication.UnicodeUTF8))
        self.chkMatchCase.setText(QtGui.QApplication.translate("FindBar", "Match Case", None, QtGui.QApplication.UnicodeUTF8))

