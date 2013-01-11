from PySide.QtGui import QIcon
from everpad.specific.unity.launcher import UnityLauncher
import os


launchers = {
    'ubuntu': UnityLauncher,
    'default': UnityLauncher,
}


def get_launcher(*args, **kwargs):
    de = os.environ.get('DESKTOP_SESSION', 'default')
    launcher = launchers.get(de, launchers['default'])
    return launcher(*args, **kwargs)


def get_tray_icon(is_black=False):
    if os.environ.get('DESKTOP_SESSION', 'default') == 'gnome':
        return QIcon.fromTheme('everpad', QIcon('../../data/everpad.png'))
    if is_black:
        return QIcon.fromTheme('everpad-black', QIcon('../../data/everpad-black.png'))
    else:
        return QIcon.fromTheme('everpad-mono', QIcon('../../data/everpad-mono.png'))
