from .service import ProviderService
from .sync.agent import SyncThread
from .tools import set_auth_token, get_auth_token, get_db_session
from ..specific import AppClass
from ..tools import print_version
from . import models
from PySide.QtCore import Slot, QSettings
import dbus
import dbus.mainloop.glib
import signal
import fcntl
import os
import getpass
import argparse
import sys
import logging


class ProviderApp(AppClass):

    def __init__(self, verbose, *args, **kwargs):
        AppClass.__init__(self, *args, **kwargs)
        self.settings = QSettings('everpad', 'everpad-provider')
        self.verbose = verbose
        session_bus = dbus.SessionBus()
        self.bus = dbus.service.BusName("com.everpad.Provider", session_bus)
        self.service = ProviderService(session_bus, '/EverpadProvider')
        self.sync_thread = SyncThread()
        self.sync_thread.sync_state_changed.connect(
            Slot(int)(self.service.sync_state_changed),
        )
        self.sync_thread.data_changed.connect(
            Slot()(self.service.data_changed),
        )
        if get_auth_token():
            self.sync_thread.start()
        self.service.qobject.authenticate_signal.connect(
            self.on_authenticated,
        )
        self.service.qobject.remove_authenticate_signal.connect(
            self.on_remove_authenticated,
        )
        self.service.qobject.terminate.connect(self.terminate)
        # Configure logger.
        self.logger = logging.getLogger('everpad-provider')
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(
            os.path.expanduser('~/.everpad/logs/everpad-provider.log'))
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.debug('Provider started.')

    @Slot(str)
    def on_authenticated(self, token):
        set_auth_token(token)
        self.sync_thread.start()

    @Slot()
    def on_remove_authenticated(self):
        self.sync_thread.quit()
        self.sync_thread.update_count = 0
        set_auth_token('')
        session = get_db_session()
        session.query(models.Note).delete(
            synchronize_session='fetch',
        )
        session.query(models.Resource).delete(
            synchronize_session='fetch',
        )
        session.query(models.Notebook).delete(
            synchronize_session='fetch',
        )
        session.query(models.Tag).delete(
            synchronize_session='fetch',
        )
        session.commit()

    def log(self, data):
        self.logger.debug(data)
        if self.verbose:
            print data

    @Slot()
    def terminate(self):
        self.sync_thread.quit()
        self.quit()


def _create_dirs(dirs):
    """Create everpad dirs"""
    for path in dirs:
        try:
            os.mkdir(os.path.expanduser(path))
        except OSError:
            continue


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    _create_dirs(['~/.everpad/', '~/.everpad/data/', '~/.everpad/logs/'])
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='verbose output')
    parser.add_argument('--version', '-v', action='store_true', help='show version')
    args = parser.parse_args(sys.argv[1:])
    if args.version:
        print_version()
    fp = open('/tmp/everpad-provider-%s.lock' % getpass.getuser(), 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        app = ProviderApp(args.verbose, sys.argv)
        app.exec_()
    except IOError:
        print("everpad-provider already ran")
    except Exception as e:
        app.logger.debug(e)

if __name__ == '__main__':
    main()
