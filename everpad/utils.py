from PySide.QtCore import QThread, Slot, Signal
import time

class SyncThread(QThread):
    """Thread for custom actions"""
    action_receive = Signal(tuple)

    @Slot(tuple)
    def action_received(self, data):
        self.queue.append(data)

    def perform(self, action, args, kwargs={}, sig=None):
        result = action(*args, **kwargs)
        if sig:
            sig.emit(result)

    def run(self):
        """Run thread with action"""
        self.queue = []
        self.action_receive.connect(self.action_received)
        while True:
            try:
                self.perform(*self.queue[0])
                self.queue = self.queue[1:]
            except IndexError:
                time.sleep(3)
        self.exit()
