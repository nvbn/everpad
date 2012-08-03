# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'editor.ui'
#
# Created: Sat Aug  4 00:35:08 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_Editor(object):
    def setupUi(self, Editor):
        Editor.setObjectName("Editor")
        Editor.resize(351, 333)
        self.centralwidget = QtGui.QWidget(Editor)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtGui.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.notebook = QtGui.QComboBox(self.centralwidget)
        self.notebook.setObjectName("notebook")
        self.horizontalLayout.addWidget(self.notebook)
        self.title = QtGui.QLineEdit(self.centralwidget)
        self.title.setObjectName("title")
        self.horizontalLayout.addWidget(self.title)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.content = QtGui.QTextEdit(self.centralwidget)
        self.content.setObjectName("content")
        self.verticalLayout.addWidget(self.content)
        self.tags = QtGui.QLineEdit(self.centralwidget)
        self.tags.setObjectName("tags")
        self.verticalLayout.addWidget(self.tags)
        Editor.setCentralWidget(self.centralwidget)
        self.menubar = QtGui.QMenuBar(Editor)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 351, 25))
        self.menubar.setObjectName("menubar")
        self.menuFIle = QtGui.QMenu(self.menubar)
        self.menuFIle.setObjectName("menuFIle")
        Editor.setMenuBar(self.menubar)
        self.actionSave = QtGui.QAction(Editor)
        self.actionSave.setObjectName("actionSave")
        self.actionSave_and_close = QtGui.QAction(Editor)
        self.actionSave_and_close.setObjectName("actionSave_and_close")
        self.actionDelete = QtGui.QAction(Editor)
        self.actionDelete.setObjectName("actionDelete")
        self.actionClose = QtGui.QAction(Editor)
        self.actionClose.setObjectName("actionClose")
        self.menuFIle.addAction(self.actionSave)
        self.menuFIle.addAction(self.actionSave_and_close)
        self.menuFIle.addAction(self.actionDelete)
        self.menuFIle.addAction(self.actionClose)
        self.menubar.addAction(self.menuFIle.menuAction())

        self.retranslateUi(Editor)
        QtCore.QMetaObject.connectSlotsByName(Editor)

    def retranslateUi(self, Editor):
        Editor.setWindowTitle(QtGui.QApplication.translate("Editor", "Everpad", None, QtGui.QApplication.UnicodeUTF8))
        self.menuFIle.setTitle(QtGui.QApplication.translate("Editor", "Note", None, QtGui.QApplication.UnicodeUTF8))
        self.actionSave.setText(QtGui.QApplication.translate("Editor", "Save", None, QtGui.QApplication.UnicodeUTF8))
        self.actionSave_and_close.setText(QtGui.QApplication.translate("Editor", "Save and close", None, QtGui.QApplication.UnicodeUTF8))
        self.actionDelete.setText(QtGui.QApplication.translate("Editor", "Delete", None, QtGui.QApplication.UnicodeUTF8))
        self.actionClose.setText(QtGui.QApplication.translate("Editor", "Close", None, QtGui.QApplication.UnicodeUTF8))

