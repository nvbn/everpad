# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'image.ui'
#
# Created: Sat Sep 29 16:13:53 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ImageDialog(object):
    def setupUi(self, ImageDialog):
        ImageDialog.setObjectName("ImageDialog")
        ImageDialog.setWindowModality(QtCore.Qt.WindowModal)
        ImageDialog.resize(248, 164)
        ImageDialog.setModal(True)
        self.gridLayout = QtGui.QGridLayout(ImageDialog)
        self.gridLayout.setObjectName("gridLayout")
        self.label = QtGui.QLabel(ImageDialog)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.widthBox = QtGui.QSpinBox(ImageDialog)
        self.widthBox.setMinimum(1)
        self.widthBox.setMaximum(99999)
        self.widthBox.setObjectName("widthBox")
        self.gridLayout.addWidget(self.widthBox, 0, 1, 1, 1)
        self.label_2 = QtGui.QLabel(ImageDialog)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.heightBox = QtGui.QSpinBox(ImageDialog)
        self.heightBox.setMinimum(1)
        self.heightBox.setMaximum(99999)
        self.heightBox.setObjectName("heightBox")
        self.gridLayout.addWidget(self.heightBox, 1, 1, 1, 1)
        self.checkBox = QtGui.QCheckBox(ImageDialog)
        self.checkBox.setChecked(True)
        self.checkBox.setObjectName("checkBox")
        self.gridLayout.addWidget(self.checkBox, 2, 0, 1, 2)
        self.buttonBox = QtGui.QDialogButtonBox(ImageDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 3, 0, 1, 2)

        self.retranslateUi(ImageDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), ImageDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), ImageDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ImageDialog)

    def retranslateUi(self, ImageDialog):
        ImageDialog.setWindowTitle(QtGui.QApplication.translate("ImageDialog", "Everpad / Image Preferences", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("ImageDialog", "Width", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("ImageDialog", "Height", None, QtGui.QApplication.UnicodeUTF8))
        self.checkBox.setText(QtGui.QApplication.translate("ImageDialog", "Discard ratio", None, QtGui.QApplication.UnicodeUTF8))

