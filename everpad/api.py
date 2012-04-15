import sys
from evernote.edam.error.ttypes import EDAMUserException
sys.path.insert(0, 'lib')
from thrift.protocol import TBinaryProtocol
from thrift.transport import THttpClient
from evernote.edam.userstore import UserStore
from evernote.edam.notestore import NoteStore
from evernote.edam.limits.constants import EDAM_NOTE_TITLE_LEN_MAX, EDAM_NOTE_CONTENT_LEN_MAX
from evernote.edam.notestore.ttypes import NoteFilter
from evernote.edam.type.ttypes import Note
from datetime import datetime


class Api(object):
    def __init__(self, username, password):
        """Init api and authenticate

        Keyword Arguments:
        username -- str
        password -- str

        Returns: None
        """
        self.username, self.password = username, password
        self.consumer_key = "nvbn"
        self.consumer_secret = "db66cc3f560645d2"
        self.evernote_host = "evernote.com"
        self.user_store_uri = "https://" + self.evernote_host + "/edam/user"
        self.note_store_uri_base = "https://" + self.evernote_host + "/edam/note/"
        self.user_store_http_client = THttpClient.THttpClient(self.user_store_uri)
        self.user_store_protocol = TBinaryProtocol.TBinaryProtocol(self.user_store_http_client)
        self.user_store = UserStore.Client(self.user_store_protocol)
        self.auth_result = self.user_store.authenticate(
            username, password,
            self.consumer_key, self.consumer_secret,
        )
        self.expire = datetime.fromtimestamp(
            float(self.auth_result.expiration) / 1000,
        )
        self.user = self.auth_result.user
        self.auth_token = self.auth_result.authenticationToken
        self.note_store_uri = self.note_store_uri_base + self.user.shardId
        self.note_store_http_client = THttpClient.THttpClient(self.note_store_uri)
        self.note_store_protocol = TBinaryProtocol.TBinaryProtocol(self.note_store_http_client)
        self.note_store = NoteStore.Client(self.note_store_protocol)
        self.notes = []

    def get_notes(self, limit=1000, words=None):
        """Get notes

        Keyword Arguments:
        limit -- int

        Returns: list
        """
        return self.note_store.findNotes(self.auth_token, NoteFilter(words=words), 0, limit).notes

    def get_note(self, id):
        """Get note

        Keyword Argument:
        id -- int

        Returns: Note
        """
        return self.note_store.getNote(self.auth_token, id, True, False, False, False)

    def update_api(self):
        """Update notes from evernote"""
        self.notes = self.note_store.findNotes(self.auth_token, NoteFilter(), 0, 1000).notes

    def update_note(self, note):
        """Update note on server side

        Keyword Arguments:
        note -- Note

        Returns: Note
        """
        self.note_store.updateNote(self.auth_token, note)
        return note

    def create_note(self, title, text):
        """Create new note

        Keyword Arguments:
        title -- unicode
        text -- unicode

        Returns: Note
        """
        return self.note_store.createNote(self.auth_token, Note(
            title=self.parse_title(title),
            content=self.parse_content(text),
        ))

    def parse_title(self, title):
        """Parse title to valid evernote format

        Keyword Arguments:
        title -- unicode

        Returns: unicode
        """
        return title[:EDAM_NOTE_TITLE_LEN_MAX].strip().encode('utf8')

    def parse_content(self, content):
        """Parse content to valid evernote xml

        Keyword Arguments:
        content -- unicode

        Returns: unicode
        """
        return (u"""
            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
            <en-note>%s</en-note>
        """ % content[:EDAM_NOTE_CONTENT_LEN_MAX]).encode('utf8')

    def remove_note(self, id):
        """Remove note on server side

        Keyword Arguments:
        id -- int

        Returns: None
        """
        self.note_store.deleteNote(self.auth_token, id)
        return id

    def find_notes(self, text):
        return self.note_store.findNotes(self.auth_token, NoteFilter(words=text), 0, 100).notes

    def check_auth(self):
        try:
            self.user_store.getUser(self.auth_token)
            return True
        except EDAMUserException:
            return False
