# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'list.ui'
#
# Created: Mon Jan 21 14:33:27 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_List(object):
    def setupUi(self, List):
        List.setObjectName("List")
        List.resize(800, 600)
        self.centralwidget = QtGui.QWidget(List)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtGui.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.splitter = QtGui.QSplitter(self.centralwidget)
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
        self.tagsList = EverpadTreeView(self.layoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tagsList.sizePolicy().hasHeightForWidth())
        self.tagsList.setSizePolicy(sizePolicy)
        self.tagsList.setMinimumSize(QtCore.QSize(200, 0))
        self.tagsList.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.tagsList.setHeaderHidden(True)
        self.tagsList.setObjectName("tagsList")
        self.verticalLayout_2.addWidget(self.tagsList)
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
        self.horizontalLayout.addWidget(self.splitter)
        List.setCentralWidget(self.centralwidget)
        self.menubar = QtGui.QMenuBar(List)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 25))
        self.menubar.setObjectName("menubar")
        List.setMenuBar(self.menubar)
        self.statusbar = QtGui.QStatusBar(List)
        self.statusbar.setObjectName("statusbar")
        List.setStatusBar(self.statusbar)

        self.retranslateUi(List)
        QtCore.QMetaObject.connectSlotsByName(List)

    def retranslateUi(self, List):
        List.setWindowTitle(QtGui.QApplication.translate("List", "MainWindow", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setToolTip(QtGui.QApplication.translate("List", "Create Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNotebookBtn.setText(QtGui.QApplication.translate("List", "Notebook", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setToolTip(QtGui.QApplication.translate("List", "Create Note", None, QtGui.QApplication.UnicodeUTF8))
        self.newNoteBtn.setText(QtGui.QApplication.translate("List", "Note", None, QtGui.QApplication.UnicodeUTF8))

from everpad.pad.treeview import EverpadTreeView
