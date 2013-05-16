from thrift.protocol import TBinaryProtocol
from thrift.transport import THttpClient
from evernote.edam.userstore import UserStore
from evernote.edam.notestore import NoteStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urlparse import urlparse
from .models import Base
from ..const import HOST, DB_PATH
from ..tools import get_proxy_config
from ..specific import get_keyring
import os


def _nocase_lower(item):
    return unicode(item).lower()


def set_auth_token(token):
    get_keyring().set_password('everpad', 'oauth_token', token)


def get_auth_token():
    return get_keyring().get_password('everpad', 'oauth_token')


def get_db_session(db_path=None):
    if not db_path:
        db_path = os.path.expanduser(DB_PATH)
    engine = create_engine('sqlite:///%s' % db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    conn = session.connection()
    conn.connection.create_function('lower', 1, _nocase_lower)
    return session


def get_user_store(auth_token=None):
    if not auth_token:
        auth_token = get_auth_token()
    user_store_uri = "https://" + HOST + "/edam/user"

    user_store_http_client = THttpClient.THttpClient(user_store_uri,
            http_proxy=get_proxy_config(urlparse(user_store_uri).scheme))
    user_store_protocol = TBinaryProtocol.TBinaryProtocol(user_store_http_client)
    return UserStore.Client(user_store_protocol)


def get_note_store(auth_token=None):
    if not auth_token:
        auth_token = get_auth_token()
    user_store = get_user_store(auth_token)
    note_store_url = user_store.getNoteStoreUrl(auth_token)
    note_store_http_client = THttpClient.THttpClient(note_store_url,
            http_proxy=get_proxy_config(urlparse(note_store_url).scheme))
    note_store_protocol = TBinaryProtocol.TBinaryProtocol(note_store_http_client)
    return NoteStore.Client(note_store_protocol)
