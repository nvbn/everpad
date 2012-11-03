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
