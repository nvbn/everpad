from PySide.QtCore import QTranslator, QLocale
from PySide.QtGui import QIcon
import dbus


def get_provider():
    provider_obj = dbus.SessionBus().get_object("com.everpad.Provider", '/EverpadProvider')
    dbus.Interface(provider_obj, "com.everpad.Provider")
    return provider_obj
provider = get_provider()

def get_icon():
    return QIcon.fromTheme('everpad', QIcon('../../everpad.png'))
