import sys
sys.path.append('..')
from everpad.provider.tools import (
    get_db_session, get_note_store,
    ACTION_CREATE, ACTION_CHANGE, 
    ACTION_DELETE,
)
from evernote.edam.type.ttypes import Note, Notebook, Tag
from everpad.provider.sync import SyncThread
from everpad.provider import models
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
import unittest



class TestProvider(unittest.TestCase):
    def setUp(self):
        self.session = get_db_session('/:memory:')
        self.store = get_note_store(token)

    def test_local_sync(self):
        return
        sc = SyncThread()
        sc.session = self.session
        sc.sq = self.session.query
        sc.note_store = self.store
        sc.auth_token = token
        note = models.Note(
            title='test', content='test',
            action=ACTION_CREATE,
        )
        self.session.add(note)
        sc.local_changes()
        self.assertEqual(
            'test',
            sc.note_store.getNote(
                token, note.guid,
                True, False, False, False,
            ).title,
            'sync simple note',
        )
        notebook = models.Notebook(
            name=str(datetime.now()),
            default=False,
            action=ACTION_CREATE,
        )
        self.session.add(notebook)
        note.notebook = notebook
        note.action = ACTION_CHANGE
        sc.local_changes()
        self.assertEqual(
            notebook.guid,
            sc.note_store.getNote(
                token, note.guid, True,
                False, False, False,
            ).notebookGuid,
            'sync note with notebook',
        )
        tag = models.Tag(
            name=str(datetime.now()),
            action=ACTION_CREATE,
        )
        self.session.add(tag)
        note.action = ACTION_CHANGE
        note.tags = [tag]
        sc.local_changes()
        self.assertEqual(
            [tag.guid],
            sc.note_store.getNote(
                token, note.guid, True,
                False, False, False,
            ).tagGuids,
            'sync note with tags',
        )
        notebook.name = str(datetime.now())
        notebook.action = ACTION_CHANGE
        sc.local_changes()
        self.assertEqual(
            notebook.name,
            sc.note_store.getNotebook(
                token, notebook.guid,
            ).name,
            'sync notebook change',
        )
        tag.name = str(datetime.now())
        tag.action = ACTION_CHANGE
        sc.local_changes()
        self.assertEqual(
            tag.name,
            sc.note_store.getTag(
                token, tag.guid,
            ).name,
            'sync tag change',
        )
        note.action = ACTION_DELETE
        sc.local_changes()
        self.assertIsNotNone(sc.note_store.getNote(
            token, note.guid, True,
            False, False, False,
        ), 'remove note')

    def test_remote_sync(self):
        sc = SyncThread()
        sc.session = self.session
        sc.sq = self.session.query
        sc.note_store = self.store
        sc.auth_token = token
        notebook = sc.note_store.createNotebook(
            sc.auth_token, Notebook(
                name=str(datetime.now()),
                defaultNotebook=False,
            ),
        )
        sc.remote_changes()
        self.assertIsNotNone(sc.sq(models.Notebook).filter(
            models.Notebook.guid == notebook.guid,
        ).one(), 'sync remote notebook')
        tag = sc.note_store.createTag(
            sc.auth_token, Tag(name=str(datetime.now())),
        )
        sc.remote_changes()
        self.assertIsNotNone(sc.sq(models.Tag).filter(
            models.Tag.guid == tag.guid,
        ).one(), 'sync remote tag')
        note = sc.note_store.createNote(
            sc.auth_token, Note(
                title='asd',
                content="""
                    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                    <en-note>%s</en-note>
                """,
            )
        )
        sc.remote_changes()
        if False:
            self.assertIsNotNone(sc.sq(models.Note).filter(
                models.Note.guid == note.guid,
            ).one(), 'sync remote note')
            notebook.name = str(datetime.now())
            sc.note_store.updateNotebook(
                sc.auth_token, notebook,
            )
            sc.remote_changes()
            self.assertEqual(sc.sq(models.Notebook).filter(
                models.Notebook.guid == notebook.guid,
            ).one().name, notebook.name, 'update local notebook')
            tag.name = str(datetime.now())
            sc.note_store.updateTag(
                sc.auth_token, tag,
            )
            sc.remote_changes()
            self.assertEqual(sc.sq(models.Tag).filter(
                models.Tag.guid == tag.guid,
            ).one().name, tag.name, 'update local tag')
            note.tagGuids = []
            sc.note_store.updateNote(
                sc.auth_token, note,
            )
            sc.remote_changes()
            self.assertEqual(sc.sq(models.Note).filter(
                models.Note.guid == note.guid,
            ).one().tags, [], 'update local note')
        sc.note_store.deleteNote(
            sc.auth_token, note.guid,
        )
        sc.remote_changes()
        with self.assertRaises(NoResultFound):
            sc.sq(models.Note).filter(
                models.Note.guid == note.guid,
            ).one().guid


if __name__ == '__main__':
    token = raw_input('enter_token:')
    unittest.main()
