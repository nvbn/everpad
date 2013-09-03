from PySide import QtCore
from datetime import datetime
from ... import const
from ...specific import AppClass
from .. import tools
from . import note, notebook, tag
from .. import models
import time
import traceback
import socket


class SyncThread(QtCore.QThread):
    """Sync notes with evernote thread"""
    force_sync_signal = QtCore.Signal()
    sync_state_changed = QtCore.Signal(int)
    data_changed = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        """Init default values"""
        QtCore.QThread.__init__(self, *args, **kwargs)
        self.app = AppClass.instance()
        self._init_timer()
        self._init_locks()

    def _init_sync(self):
        """Init sync"""
        self.status = const.STATUS_NONE
        self.last_sync = datetime.now()
        self.sync_state = self.session.query(models.Sync).first()
        if not self.sync_state:
            self.sync_state = models.Sync(
                update_count=0, last_sync=self.last_sync)
            self.session.add(self.sync_state)
            self.session.commit()

    def _init_timer(self):
        """Init timer"""
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.sync)
        self.update_timer()

    def _init_locks(self):
        """Init locks"""
        self.wait_condition = QtCore.QWaitCondition()
        self.mutex = QtCore.QMutex()

    def update_timer(self):
        """Update sync timer"""
        self.timer.stop()
        delay = int(self.app.settings.value('sync_delay') or 0)
        if not delay:
            delay = const.DEFAULT_SYNC_DELAY

        if delay != const.SYNC_MANUAL:
            self.timer.start(delay)

    def run(self):
        """Run thread"""
        self._init_db()
        self._init_network()
        self._init_sync()
        while True:
            self.mutex.lock()
            self.wait_condition.wait(self.mutex)
            self.perform()
            self.mutex.unlock()
            time.sleep(1)  # prevent cpu eating

    def _init_db(self):
        """Init database"""
        self.session = tools.get_db_session()

    def _init_network(self):
        """Init connection to remote server"""
        while True:
            try:
                self.auth_token = tools.get_auth_token()
                self.note_store = tools.get_note_store(self.auth_token)
                self.user_store = tools.get_user_store(self.auth_token)
                break
            except socket.error:
                time.sleep(30)

    def _need_to_update(self):
        """Check need for update notes"""
        self.app.log('Checking need for update notes.')
        # Try to update_count.
        try:
            update_count = self.note_store.getSyncState(
                self.auth_token).updateCount
        except socket.error, e:
            self.app.log(
                "Couldn't connect to remote server. Got: %s" %
                traceback.format_exc())
            # This is most likely a network failure. Return False so
            # everpad-provider won't lock up and can try to sync up in the
            # next run.
            return False
        #XXX: matsubara probably innefficient as it does a SQL each time it
        # accesses the update_count attr?
        self.app.log("Local update count: %s Remote update count: %s" % (
            self.sync_state.update_count, update_count))
        reason = update_count != self.sync_state.update_count
        self.sync_state.update_count = update_count
        return reason

    def force_sync(self):
        """Start sync"""
        self.timer.stop()
        self.sync()
        self.update_timer()

    @QtCore.Slot()
    def sync(self):
        """Do sync"""
        self.wait_condition.wakeAll()

    def perform(self):
        """Perform all sync"""
        self.app.log("Performing sync")
        self.status = const.STATUS_SYNC
        self.last_sync = datetime.now()
        self.sync_state_changed.emit(const.SYNC_STATE_START)

        need_to_update = self._need_to_update()

        try:
            if need_to_update:
                self.remote_changes()
            self.local_changes()
        except Exception, e:  # maybe log this
            self.session.rollback()
            self._init_db()
            self.app.log(e)
        finally:
            self.sync_state_changed.emit(const.SYNC_STATE_FINISH)
            self.status = const.STATUS_NONE
            self.all_notes = None

        self.data_changed.emit()
        self.app.log("Sync performed.")

    def _get_sync_args(self):
        """Get sync arguments"""
        return self.auth_token, self.session, self.note_store, self.user_store

    def local_changes(self):
        """Send local changes to evernote server"""
        self.app.log('Running local_changes()')
        self.sync_state_changed.emit(const.SYNC_STATE_NOTEBOOKS_LOCAL)
        notebook.PushNotebook(*self._get_sync_args()).push()

        self.sync_state_changed.emit(const.SYNC_STATE_TAGS_LOCAL)
        tag.PushTag(*self._get_sync_args()).push()

        self.sync_state_changed.emit(const.SYNC_STATE_NOTES_LOCAL)
        note.PushNote(*self._get_sync_args()).push()

    def remote_changes(self):
        """Receive remote changes from evernote"""
        self.app.log('Running remote_changes()')
        self.sync_state_changed.emit(const.SYNC_STATE_NOTEBOOKS_REMOTE)
        notebook.PullNotebook(*self._get_sync_args()).pull()

        self.sync_state_changed.emit(const.SYNC_STATE_TAGS_REMOTE)
        tag.PullTag(*self._get_sync_args()).pull()

        self.sync_state_changed.emit(const.SYNC_STATE_NOTES_REMOTE)
        note.PullNote(*self._get_sync_args()).pull()
