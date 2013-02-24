# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'share_note.ui'
#
# Created: Tue Jan 22 22:46:18 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ShareNote(object):
    def setupUi(self, ShareNote):
        ShareNote.setObjectName("ShareNote")
        ShareNote.resize(442, 197)
        ShareNote.setModal(True)
        self.verticalLayout = QtGui.QVBoxLayout(ShareNote)
        self.verticalLayout.setObjectName("verticalLayout")
        self.waitText = QtGui.QLabel(ShareNote)
        font = QtGui.QFont()
        font.setPointSize(18)
        self.waitText.setFont(font)
        self.waitText.setScaledContents(False)
        self.waitText.setAlignment(QtCore.Qt.AlignCenter)
        self.waitText.setObjectName("waitText")
        self.verticalLayout.addWidget(self.waitText)
        self.sharedWidget = QtGui.QWidget(ShareNote)
        self.sharedWidget.setObjectName("sharedWidget")
        self.horizontalLayout_2 = QtGui.QHBoxLayout(self.sharedWidget)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.sharedBox = QtGui.QVBoxLayout()
        self.sharedBox.setObjectName("sharedBox")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtGui.QLabel(self.sharedWidget)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.shareLink = QtGui.QLineEdit(self.sharedWidget)
        self.shareLink.setReadOnly(True)
        self.shareLink.setObjectName("shareLink")
        self.horizontalLayout.addWidget(self.shareLink)
        self.sharedBox.addLayout(self.horizontalLayout)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.copyButton = QtGui.QPushButton(self.sharedWidget)
        self.copyButton.setObjectName("copyButton")
        self.horizontalLayout_3.addWidget(self.copyButton)
        self.cancelButton = QtGui.QPushButton(self.sharedWidget)
        self.cancelButton.setObjectName("cancelButton")
        self.horizontalLayout_3.addWidget(self.cancelButton)
        self.sharedBox.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_2.addLayout(self.sharedBox)
        self.verticalLayout.addWidget(self.sharedWidget)

        self.retranslateUi(ShareNote)
        QtCore.QMetaObject.connectSlotsByName(ShareNote)

    def retranslateUi(self, ShareNote):
        ShareNote.setWindowTitle(QtGui.QApplication.translate("ShareNote", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.waitText.setText(QtGui.QApplication.translate("ShareNote", "wait_text", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("ShareNote", "You can share note with link: ", None, QtGui.QApplication.UnicodeUTF8))
        self.copyButton.setText(QtGui.QApplication.translate("ShareNote", "Copy url", None, QtGui.QApplication.UnicodeUTF8))
        self.cancelButton.setText(QtGui.QApplication.translate("ShareNote", "Cancel sharing", None, QtGui.QApplication.UnicodeUTF8))

