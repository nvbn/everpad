# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './tableinsert.ui'
#
# Created: Sun Oct  7 06:22:18 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_TableInsertDialog(object):
    def setupUi(self, TableInsertDialog):
        TableInsertDialog.setObjectName("TableInsertDialog")
        TableInsertDialog.setWindowModality(QtCore.Qt.WindowModal)
        TableInsertDialog.resize(433, 191)
        self.buttonBox = QtGui.QDialogButtonBox(TableInsertDialog)
        self.buttonBox.setGeometry(QtCore.QRect(80, 150, 341, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayoutWidget = QtGui.QWidget(TableInsertDialog)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(10, 10, 411, 121))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtGui.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.width = QtGui.QLineEdit(self.gridLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.width.sizePolicy().hasHeightForWidth())
        self.width.setSizePolicy(sizePolicy)
        self.width.setObjectName("width")
        self.gridLayout.addWidget(self.width, 2, 1, 1, 1)
        self.label_2 = QtGui.QLabel(self.gridLayoutWidget)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.rows = QtGui.QLineEdit(self.gridLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.rows.sizePolicy().hasHeightForWidth())
        self.rows.setSizePolicy(sizePolicy)
        self.rows.setObjectName("rows")
        self.gridLayout.addWidget(self.rows, 0, 1, 1, 1)
        self.label = QtGui.QLabel(self.gridLayoutWidget)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.columns = QtGui.QLineEdit(self.gridLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.columns.sizePolicy().hasHeightForWidth())
        self.columns.setSizePolicy(sizePolicy)
        self.columns.setObjectName("columns")
        self.gridLayout.addWidget(self.columns, 1, 1, 1, 1)
        self.label_3 = QtGui.QLabel(self.gridLayoutWidget)
        self.label_3.setObjectName("label_3")
        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)
        self.widthType = QtGui.QComboBox(self.gridLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widthType.sizePolicy().hasHeightForWidth())
        self.widthType.setSizePolicy(sizePolicy)
        self.widthType.setObjectName("widthType")
        self.widthType.addItem("")
        self.widthType.addItem("")
        self.gridLayout.addWidget(self.widthType, 2, 2, 1, 1)

        self.retranslateUi(TableInsertDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), TableInsertDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), TableInsertDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(TableInsertDialog)

    def retranslateUi(self, TableInsertDialog):
        TableInsertDialog.setWindowTitle(QtGui.QApplication.translate("TableInsertDialog", "Everpad / Insert Table", None, QtGui.QApplication.UnicodeUTF8))
        self.width.setText(QtGui.QApplication.translate("TableInsertDialog", "100", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("TableInsertDialog", "Columns:", None, QtGui.QApplication.UnicodeUTF8))
        self.rows.setText(QtGui.QApplication.translate("TableInsertDialog", "2", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("TableInsertDialog", "Rows:", None, QtGui.QApplication.UnicodeUTF8))
        self.columns.setText(QtGui.QApplication.translate("TableInsertDialog", "2", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("TableInsertDialog", "Width:", None, QtGui.QApplication.UnicodeUTF8))
        self.widthType.setItemText(0, QtGui.QApplication.translate("TableInsertDialog", "% of page", None, QtGui.QApplication.UnicodeUTF8))
        self.widthType.setItemText(1, QtGui.QApplication.translate("TableInsertDialog", "pixels", None, QtGui.QApplication.UnicodeUTF8))

