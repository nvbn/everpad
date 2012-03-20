from functools import wraps
from PySide.QtCore import QThread

class ActionThread(QThread):
    """Thread for custom actions"""

    def __init__(self, action, *args, **kwargs):
        """Init thread with action

        Keyword Arguments:
        action -- callable

        Returns: None
        """
        self.action = action
        QThread.__init__(self, *args, **kwargs)

    def run(self):
        """Run thread with action"""
        self.action()
        self.exit()

def action_thread(fnc):
    @wraps(fnc)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, '_action_threads'):
            self._action_threads = []
        elif type(self._action_threads) is not list:
            raise TypeError('_action_threads mus by list')
        thread = ActionThread(lambda: fnc(self, *args, **kwargs))
        self._action_threads.append(thread)
        thread.start()
        return True
    return wrapper
