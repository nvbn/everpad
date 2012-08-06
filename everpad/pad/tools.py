from PySide.QtCore import QTranslator, QLocale
from PySide.QtGui import QIcon


def get_icon():
    return QIcon.fromTheme('everpad', QIcon('../../everpad.png'))
