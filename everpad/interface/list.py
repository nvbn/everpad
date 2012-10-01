# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'list.ui'
#
# Created: Sun Sep 30 17:20:38 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_List(object):
    def setupUi(self, List):
        List.setObjectName("List")
        List.resize(800, 600)
        List.setModal(False)
        self.verticalLayout = QtGui.QVBoxLayout(List)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.notebooksList = QtGui.QListView(List)
        self.notebooksList.setMinimumSize(QtCore.QSize(200, 0))
        self.notebooksList.setMaximumSize(QtCore.QSize(220, 16777215))
        self.notebooksList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.notebooksList.setObjectName("notebooksList")
        self.horizontalLayout.addWidget(self.notebooksList)
        self.notesList = QtGui.QListView(List)
        self.notesList.setMinimumSize(QtCore.QSize(300, 0))
        self.notesList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.notesList.setObjectName("notesList")
        self.horizontalLayout.addWidget(self.notesList)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(List)
        QtCore.QMetaObject.connectSlotsByName(List)

    def retranslateUi(self, List):
        List.setWindowTitle(QtGui.QApplication.translate("List", "Everpad / All Notes", None, QtGui.QApplication.UnicodeUTF8))

