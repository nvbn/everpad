# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'notebook.ui'
#
# Created: Sun Aug 19 18:09:52 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_Notebook(object):
    def setupUi(self, Notebook):
        Notebook.setObjectName("Notebook")
        Notebook.resize(296, 60)
        self.horizontalLayout = QtGui.QHBoxLayout(Notebook)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.name = QtGui.QLabel(Notebook)
        font = QtGui.QFont()
        font.setWeight(75)
        font.setBold(True)
        self.name.setFont(font)
        self.name.setObjectName("name")
        self.verticalLayout.addWidget(self.name)
        self.content = QtGui.QLabel(Notebook)
        font = QtGui.QFont()
        font.setWeight(50)
        font.setBold(False)
        self.content.setFont(font)
        self.content.setObjectName("content")
        self.verticalLayout.addWidget(self.content)
        self.horizontalLayout.addLayout(self.verticalLayout)
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.actionBtn = QtGui.QPushButton(Notebook)
        self.actionBtn.setText("")
        self.actionBtn.setObjectName("actionBtn")
        self.horizontalLayout.addWidget(self.actionBtn)

        self.retranslateUi(Notebook)
        QtCore.QMetaObject.connectSlotsByName(Notebook)

    def retranslateUi(self, Notebook):
        Notebook.setWindowTitle(QtGui.QApplication.translate("Notebook", "Form", None, QtGui.QApplication.UnicodeUTF8))
        self.name.setText(QtGui.QApplication.translate("Notebook", "Notebook name", None, QtGui.QApplication.UnicodeUTF8))
        self.content.setText(QtGui.QApplication.translate("Notebook", "Contains 5 notes", None, QtGui.QApplication.UnicodeUTF8))

