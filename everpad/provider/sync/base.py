from ...specific import AppClass


class BaseSync(object):
    """Base class for sync"""

    def __init__(self, auth_token, session, note_store, user_store):
        """Set shortcuts"""
        self.auth_token = auth_token
        self.session = session
        self.note_store = note_store
        self.user_store = user_store
        self.app = AppClass.instance()
