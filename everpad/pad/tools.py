from PySide.QtCore import QTranslator, QLocale
from PySide.QtGui import QIcon


def get_icon(name):
    fallback_path = '/opt/extras.ubuntu.com/everpad/icons/%s.png' % name
    return QIcon.fromTheme(name, QIcon(fallback_path))
