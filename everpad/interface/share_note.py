# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'share_note.ui'
#
# Created: Tue Jan 22 21:19:23 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ShareNote(object):
    def setupUi(self, ShareNote):
        ShareNote.setObjectName("ShareNote")
        ShareNote.resize(442, 197)
        self.verticalLayout = QtGui.QVBoxLayout(ShareNote)
        self.verticalLayout.setObjectName("verticalLayout")
        self.waitText = QtGui.QLabel(ShareNote)
        self.waitText.setObjectName("waitText")
        self.verticalLayout.addWidget(self.waitText)
        self.sharedBox = QtGui.QVBoxLayout()
        self.sharedBox.setObjectName("sharedBox")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtGui.QLabel(ShareNote)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.shareLink = QtGui.QLabel(ShareNote)
        self.shareLink.setObjectName("shareLink")
        self.horizontalLayout.addWidget(self.shareLink)
        self.sharedBox.addLayout(self.horizontalLayout)
        self.pushButton = QtGui.QPushButton(ShareNote)
        self.pushButton.setObjectName("pushButton")
        self.sharedBox.addWidget(self.pushButton)
        self.verticalLayout.addLayout(self.sharedBox)

        self.retranslateUi(ShareNote)
        QtCore.QMetaObject.connectSlotsByName(ShareNote)

    def retranslateUi(self, ShareNote):
        ShareNote.setWindowTitle(QtGui.QApplication.translate("ShareNote", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.waitText.setText(QtGui.QApplication.translate("ShareNote", "wait_text", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("ShareNote", "You can share note with link: ", None, QtGui.QApplication.UnicodeUTF8))
        self.shareLink.setText(QtGui.QApplication.translate("ShareNote", "note_link", None, QtGui.QApplication.UnicodeUTF8))
        self.pushButton.setText(QtGui.QApplication.translate("ShareNote", "Cancel sharing", None, QtGui.QApplication.UnicodeUTF8))

