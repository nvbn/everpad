# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'list.ui'
#
# Created: Sat Oct 13 16:54:46 2012
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
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.newNotebookBtn = QtGui.QPushButton(List)
        self.newNotebookBtn.setObjectName("newNotebookBtn")
        self.horizontalLayout_2.addWidget(self.newNotebookBtn)
        self.newNoteBtn = QtGui.QPushButton(List)
        self.newNoteBtn.setObjectName("newNoteBtn")
        self.horizontalLayout_2.addWidget(self.newNoteBtn)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)
        self.notebooksList = QtGui.QListView(List)
        self.notebooksList.setMinimumSize(QtCore.QSize(200, 0))
        self.notebooksList.setMaximumSize(QtCore.QSize(220, 16777215))
        self.notebooksList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.notebooksList.setObjectName("notebooksList")
        self.verticalLayout_2.addWidget(self.notebooksList)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.notesList = QtGui.QTreeView(List)
        self.notesList.setSortingEnabled(True)
        self.notesList.setObjectName("notesList")
        self.notesList.header().setDefaultSectionSize(200)
        self.notesList.header().setSortIndicatorShown(True)
        self.horizontalLayout.addWidget(self.notesList)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(List)
        QtCore.QMetaObject.connectSlotsByName(List)

    def retranslateUi(self, List):
        List.setWindowTitle(QtGui.QApplication.translate("List", "Everpad / All Notes", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setToolTip(QtGui.QApplication.translate("List", "Create Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setText(QtGui.QApplication.translate("List", "Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setToolTip(QtGui.QApplication.translate("List", "Create Note", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setText(QtGui.QApplication.translate("List", "Note", None, QtGui.QApplication.UnicodeUTF8))

