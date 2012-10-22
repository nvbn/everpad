# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'everpad/interface/list.ui'
#
# Created: Mon Oct 22 03:22:26 2012
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
        self.splitter = QtGui.QSplitter(List)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setObjectName("splitter")
        self.layoutWidget = QtGui.QWidget(self.splitter)
        self.layoutWidget.setObjectName("layoutWidget")
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.layoutWidget)
        self.verticalLayout_2.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.newNotebookBtn = QtGui.QPushButton(self.layoutWidget)
        self.newNotebookBtn.setObjectName("newNotebookBtn")
        self.horizontalLayout_2.addWidget(self.newNotebookBtn)
        self.newNoteBtn = QtGui.QPushButton(self.layoutWidget)
        self.newNoteBtn.setObjectName("newNoteBtn")
        self.horizontalLayout_2.addWidget(self.newNoteBtn)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)
        self.notebooksList = EverpadTreeView(self.layoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.notebooksList.sizePolicy().hasHeightForWidth())
        self.notebooksList.setSizePolicy(sizePolicy)
        self.notebooksList.setMinimumSize(QtCore.QSize(200, 0))
        self.notebooksList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.notebooksList.setHeaderHidden(True)
        self.notebooksList.setObjectName("notebooksList")
        self.verticalLayout_2.addWidget(self.notebooksList)
        self.notesList = QtGui.QTreeView(self.splitter)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.notesList.sizePolicy().hasHeightForWidth())
        self.notesList.setSizePolicy(sizePolicy)
        self.notesList.setMinimumSize(QtCore.QSize(300, 0))
        self.notesList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.notesList.setSortingEnabled(True)
        self.notesList.setObjectName("notesList")
        self.notesList.header().setDefaultSectionSize(200)
        self.notesList.header().setSortIndicatorShown(True)
        self.verticalLayout.addWidget(self.splitter)

        self.retranslateUi(List)
        QtCore.QMetaObject.connectSlotsByName(List)

    def retranslateUi(self, List):
        List.setWindowTitle(QtGui.QApplication.translate("List", "Everpad / All Notes", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setToolTip(QtGui.QApplication.translate("List", "Create Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setText(QtGui.QApplication.translate("List", "Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setToolTip(QtGui.QApplication.translate("List", "Create Note", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setText(QtGui.QApplication.translate("List", "Note", None, QtGui.QApplication.UnicodeUTF8))

from everpad.pad.treeview import EverpadTreeView
