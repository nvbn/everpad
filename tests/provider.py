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
from everpad.provider.service import ProviderService
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
import unittest



class TestProvider(unittest.TestCase):
    def setUp(self):
        self.session = get_db_session(':memory:')
        self.store = get_note_store(token)
        self.sc = SyncThread()
        self.sc.session = self.session
        self.sc.sq = self.session.query
        self.sc.note_store = self.store
        self.sc.auth_token = token
        self.serv = ProviderService()
        self.serv._session = self.session
        models.Note.session = self.session  # hack for test

    def test_local_sync(self):
        note = models.Note(
            title='test', content='test',
            action=ACTION_CREATE,
        )
        self.session.add(note)
        self.sc.local_changes()
        self.assertEqual(
            'test',
            self.sc.note_store.getNote(
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
        self.sc.local_changes()
        self.assertEqual(
            notebook.guid,
            self.sc.note_store.getNote(
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
        self.sc.local_changes()
        self.assertEqual(
            [tag.guid],
            self.sc.note_store.getNote(
                token, note.guid, True,
                False, False, False,
            ).tagGuids,
            'sync note with tags',
        )
        notebook.name = str(datetime.now())
        notebook.action = ACTION_CHANGE
        self.sc.local_changes()
        self.assertEqual(
            notebook.name,
            self.sc.note_store.getNotebook(
                token, notebook.guid,
            ).name,
            'sync notebook change',
        )
        tag.name = str(datetime.now())
        tag.action = ACTION_CHANGE
        self.sc.local_changes()
        self.assertEqual(
            tag.name,
            self.sc.note_store.getTag(
                token, tag.guid,
            ).name,
            'sync tag change',
        )
        note.action = ACTION_DELETE
        self.sc.local_changes()
        self.assertIsNotNone(self.sc.note_store.getNote(
            token, note.guid, True,
            False, False, False,
        ), 'remove note')

    def test_remote_sync(self):
        notebook = self.sc.note_store.createNotebook(
            self.sc.auth_token, Notebook(
                name=str(datetime.now()),
                defaultNotebook=False,
            ),
        )
        self.sc.remote_changes()
        self.assertIsNotNone(self.sc.sq(models.Notebook).filter(
            models.Notebook.guid == notebook.guid,
        ).one(), 'sync remote notebook')
        tag = self.sc.note_store.createTag(
            self.sc.auth_token, Tag(name=str(datetime.now())),
        )
        self.sc.remote_changes()
        self.assertIsNotNone(self.sc.sq(models.Tag).filter(
            models.Tag.guid == tag.guid,
        ).one(), 'sync remote tag')
        note = self.sc.note_store.createNote(
            self.sc.auth_token, Note(
                title='asd',
                content="""
                    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                    <en-note>%s</en-note>
                """,
            )
        )
        self.sc.remote_changes()
        self.assertIsNotNone(self.sc.sq(models.Note).filter(
            models.Note.guid == note.guid,
        ).one(), 'sync remote note')
        notebook.name = str(datetime.now())
        self.sc.note_store.updateNotebook(
            self.sc.auth_token, notebook,
        )
        self.sc.remote_changes()
        self.assertEqual(self.sc.sq(models.Notebook).filter(
            models.Notebook.guid == notebook.guid,
        ).one().name, notebook.name, 'update local notebook')
        tag.name = str(datetime.now())
        self.sc.note_store.updateTag(
            self.sc.auth_token, tag,
        )
        self.sc.remote_changes()
        self.assertEqual(self.sc.sq(models.Tag).filter(
            models.Tag.guid == tag.guid,
        ).one().name, tag.name, 'update local tag')
        note.tagGuids = []
        self.sc.note_store.updateNote(
            self.sc.auth_token, note,
        )
        self.sc.remote_changes()
        self.assertEqual(self.sc.sq(models.Note).filter(
            models.Note.guid == note.guid,
        ).one().tags, [], 'update local note')
        self.sc.note_store.deleteNote(
            self.sc.auth_token, note.guid,
        )
        self.sc.remote_changes()
        # with self.assertRaises(NoResultFound):  fails via evernote issue =(
        #     sc.sq(models.Note).filter(
        #         models.Note.guid == note.guid,
        #     ).one().guid

    def test_service_get_note(self):
        note = models.Note(title='123', content='123', action=ACTION_CREATE)
        self.session.add(note)
        self.session.commit()
        self.assertEqual(
            self.serv.get_note(note.id),
            (note.id, '123', '123', None, None, None, []),
            'get note from service',
        )

    def test_service_find_notes(self):
        note = models.Note(title='q ab cd', content='123', action=ACTION_CREATE)
        tag = models.Tag(name='eee')
        notebook = models.Notebook(name='123')
        self.session.add_all([note, tag, notebook])
        note.tags = [tag]
        note.notebook = notebook
        self.session.commit()
        self.assertEqual(
            self.serv.find_notes('ab cd', [notebook.id], [tag.id]),
            [(note.id, u'q ab cd', u'123', None, None, notebook.id, [u'eee'])],
            'find notes via service',
        )

    def test_service_list_notebooks(self):
        notebook = models.Notebook(name='a123')
        self.session.add(notebook)
        self.session.commit()
        self.assertEqual(
            self.serv.list_notebooks(),
            [(notebook.id, u'a123', None)],
            'list notebooks',
        )

    def test_service_get_notebook(self):
        notebook = models.Notebook(name='a123', default=True)
        self.session.add(notebook)
        self.session.commit()
        self.assertEqual(
            self.serv.get_notebook(notebook.id),
            (notebook.id, u'a123', True),
            'get notebook',
        )

    def test_service_list_tags(self):
        tag = models.Tag(name='123')
        self.session.add(tag)
        self.session.commit()
        self.assertEqual(
            self.serv.list_tags(),
            [(tag.id, u'123')],
            'list tags'
        )

    def test_service_create_note(self):
        notebook = models.Notebook(name='a123', default=True)
        self.session.add(notebook)
        self.session.commit()
        note = (None, u'q ab cd', u'123', None, None, notebook.id, [u'eee'])
        self.assertEqual(
            self.serv.create_note(note),
            (1, u'q ab cd', u'123', None, None, notebook.id, [u'eee']),
            'create note via service',
        )

    def test_service_update_note(self):
        notebook = models.Notebook(name='a123', default=True)
        note = models.Note(
            title='123', content='123',
            notebook=notebook,
        )
        self.session.add_all([notebook, note])
        self.session.commit()
        result = self.serv.update_note(
            (note.id, u'q ab cd', u'123', None, None, notebook.id, [u'eee']),
        )
        self.assertEqual(result,
            (note.id, u'q ab cd', u'123', None, None, notebook.id, [u'eee']),
            'update note',
        )

    def test_service_delete_note(self):
        notebook = models.Notebook(name='a123', default=True)
        note = models.Note(
            title='123', content='123',
            notebook=notebook,
        )
        self.session.add_all([notebook, note])
        self.session.commit()
        self.serv.delete_note(note.id)
        self.assertEqual(note.action, ACTION_DELETE, 'delete note')

    def test_service_create_notebook(self):
        notebook = self.serv.create_notebook(
            (None, u'a123', True),
        )
        self.assertEqual(notebook,
            (1, u'a123', True),
            'create notebook',
        )


if __name__ == '__main__':
    token = raw_input('enter_token:')
    unittest.main()
