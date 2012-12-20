import sys
sys.path.insert(0, '..')
from settings import TOKEN
from everpad.provider.tools import (
    get_db_session, get_note_store,
    ACTION_CREATE, ACTION_CHANGE, 
    ACTION_DELETE,
)
from evernote.edam.type.ttypes import Note, Notebook, Tag
from everpad.provider.sync import SyncThread
from everpad.provider import models
from everpad.provider.service import ProviderService
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
import unittest


class SyncTestCase(unittest.TestCase):
    pass
