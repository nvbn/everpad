# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')
from settings import TOKEN
from everpad.const import HOST
from everpad.provider.sync import SyncAgent, NotebookSync
from everpad.provider.tools import get_db_session, get_note_store
from everpad.provider.models import (
    Note, Notebook, Place, Tag, Resource, ACTION_CREATE,
    ACTION_CHANGE, ACTION_NONE, ACTION_DELETE, ACTION_CONFLICT,
    SHARE_NONE, SHARE_NEED_SHARE, SHARE_SHARED, SHARE_NEED_STOP,
)
from evernote.edam.type import ttypes
from evernote import edam
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
from mock import MagicMock
import unittest
import os
import time


resource_path = os.path.join(os.path.dirname(__file__), '../test.png')


class FakeSyncThread(SyncAgent):
    def __init__(self):
        self.logs = []
        self.app = type('fake', (object,), {
            'log': self.log,
        })
        self.update_count = 0
        self.session = get_db_session()
        self.sq = self.session.query
        self.auth_token = TOKEN
        if self._need_to_update():
            self.need_to_update = True
        else:
            self.need_to_update = False

    @property
    def note_store(self):
        if not hasattr(self, '_note_store'):
            self._note_store = MagicMock()
        return self._note_store

    @note_store.setter
    def note_store(self, store):
        self._note_store = store

    @property
    def all_notes(self):
        """Prevent caching"""
        return self._iter_all_notes()

    def _remove_all_notes(self):
        """Remove all notes on evernote"""
        for note in self.all_notes:
            self.note_store.deleteNote(self.auth_token, note.guid)

    def log(self, val):
        self.logs.append(val)


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.assertEqual(
            HOST, 'sandbox.evernote.com',
            """
            Run tests only wiht sandbox,
            it's remove all you notes!!!
            """,
        )
        self.sync = FakeSyncThread()
        self.session = self.sync.session
        self.sq = self.sync.session.query
        self.auth_token = self.sync.auth_token
        self.note_store = self.sync.note_store

    def _create_remote_note(self, **params):
        self.sync._remove_all_notes()
        # prevent syncing notes without received notebook
        self.sync.notebooks_remote()
        remote_notebook = self.note_store.getDefaultNotebook(self.auth_token)
        return self.note_store.createNote(self.auth_token, ttypes.Note(
            title='test',
            content=u"""
                <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                <en-note>test</en-note>
            """,
            notebookGuid=remote_notebook.guid,
            created=int(time.time() * 1000),
            updated=int(time.time() * 1000),
            **params
        ))

    def _create_note(self, **params):
        remote_notebook = self._default_notebook()
        if not 'attributes' in params:
            params['attributes'] = MagicMock()
            params['attributes'].placeName = None
            params['attributes'].shareDate = None
        return ttypes.Note(
            title='test',
            content=u"""
                <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                <en-note>test</en-note>
            """,
            notebookGuid=remote_notebook.guid,
            created=int(time.time() * 1000),
            updated=int(time.time() * 1000),
            **params
        )

    def _default_notebook(self):
        """Get default notebook"""
        remote_notebook = ttypes.Notebook(
            name='default',
        )
        notebook = Notebook(guid='guid')
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()

        self.sync._note_store.getDefaultNotebook = MagicMock()
        self.sync._note_store.getDefaultNotebook.return_value = remote_notebook

        return notebook

    def _get_default_notebook(self):
        """Get default notebook"""
        remote_notebook = self.sync._note_store.getDefaultNotebook(self.auth_token)
        notebook = Notebook(guid=remote_notebook.guid)
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()
        return notebook

    def _mock_return_one_note(self, remote):
        """Mock return just one note"""
        self.sync._iter_all_notes = MagicMock()
        self.sync._iter_all_notes.return_value = [remote]

        self.sync.note_store.getNote = MagicMock()
        self.sync.note_store.getNote.return_value = remote

    def test_sync_notes_with_lonlat(self):
        """Test sync notes with lonlat"""
        remote = self._create_note(
            attributes=ttypes.NoteAttributes(
                longitude=80,
                latitude=60,
            ),
            guid='79a423bd-0b44-4925-97c8-b3e2c225dac6',
        )

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        self.assertIsNotNone(note.place)

    def test_sync_notes_with_place_name(self):
        """Test sync notes with place"""
        place_name = 'test place'
        remote = self._create_note(
            attributes=ttypes.NoteAttributes(
                placeName=place_name,
            ),
            guid='79a423bd-0b44-4925-97c8-b3e2c225dac6',
        )

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        self.assertEqual(
            note.place.name, place_name,
        )

    def test_local_notebooks(self):
        """Test sync local notebooks"""
        name = str(datetime.now())
        notebook = Notebook(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(notebook)
        self.session.commit()

        self.sync.note_store.createNotebook = MagicMock()
        self.sync.note_store.createNotebook.return_value.guid = 'guid'

        self.sync.notebooks_local()

        self.assertEqual(notebook.action, ACTION_NONE)

        notebook_remote = self.sync.note_store.createNotebook.call_args_list[0][0][1]

        self.assertEqual(notebook.name, notebook_remote.name)

        notebook.name += '*'
        notebook.action = ACTION_CHANGE

        self.sync.note_store.updateNotebook = MagicMock()
        self.sync.note_store.updateNotebook.return_value.guid = 'guid'

        self.sync.notebooks_local()
        self.assertEqual(notebook.action, ACTION_NONE)

        notebook_remote = self.sync.note_store.updateNotebook.call_args_list[0][0][1]

        self.assertEqual(notebook.name, notebook_remote.name)

    def test_local_tags(self):
        """Test sync local tags"""
        name = str(datetime.now())
        tag = Tag(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(tag)
        self.session.commit()

        self.sync.note_store.createTag = MagicMock()
        self.sync.note_store.createTag.return_value.guid = 'guid'

        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)

        tag_remote = self.sync.note_store.createTag.call_args_list[0][0][1]
        self.assertEqual(tag.name, tag_remote.name)
        tag.name += '*'
        tag.action = ACTION_CHANGE

        self.sync.note_store.updateTag = MagicMock()

        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)

        tag_remote = self.sync.note_store.updateTag.call_args_list[0][0][1]

        self.assertEqual(tag.name, tag_remote.name)

    def test_local_notes(self):
        """Test local notes sync"""
        notebook = self._default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
        )
        self.session.add(note)
        self.session.commit()

        self.sync.note_store.createNote = MagicMock()
        self.sync.note_store.createNote.return_value.guid = 'guid'

        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)

        note_remote = self.sync.note_store.createNote.call_args_list[0][0][1]

        self.assertEqual(notebook.guid, note_remote.notebookGuid)

        note.title += '*'
        note.action = ACTION_CHANGE

        self.sync.note_store.updateNote = MagicMock()

        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)

        note_remote = self.sync.note_store.updateNote.call_args_list[0][0][1]

        self.assertEqual(note.title, note_remote.title)
        note.action = ACTION_DELETE

        self.sync.note_store.deleteNote = MagicMock()

        self.sync.notes_local()
        self.assertEqual(note.guid, self.sync.note_store.deleteNote.call_args_list[0][0][1])

        with self.assertRaises(NoResultFound):
            self.sq(Note).filter(
                Note.guid == note.guid,
            ).one()

    def test_local_resources(self):
        """Test local resources"""
        notebook = self._default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
        )
        self.session.add(note)
        self.session.commit()

        res = Resource(
            note_id=note.id, file_name='test.png',
            file_path=resource_path, mime='image/png',
            action=ACTION_CREATE,
        )
        self.session.add(res)
        self.session.commit()

        self.sync.note_store.createNote = MagicMock()
        self.sync.note_store.createNote.return_value.guid = 'guid'

        self.sync.notes_local()
        note_remote = self.sync.note_store.createNote.call_args_list[0][0][1]

        self.assertEqual('test.png', note_remote.resources[0].attributes.fileName)
        self.session.delete(res)
        self.session.commit()
        note.action = ACTION_CHANGE

        self.sync.note_store.updateNote = MagicMock()

        self.sync.notes_local()
        note_remote = self.sync.note_store.updateNote.call_args_list[0][0][1]
        self.assertEqual(note_remote.resources, [])

    def test_remote_notebooks(self):
        """Test syncing remote notebooks"""
        name = str(datetime.now())
        guid = 'guid'

        self.note_store.listNotebooks = MagicMock()
        self.note_store.listNotebooks.return_value = [ttypes.Notebook(
            name=name,
            guid=guid,
            serviceUpdated=0,
        )]

        self.sync.notebooks_remote()
        notebook = self.sq(Notebook).filter(
            Notebook.guid == guid,
        ).one()

        self.assertEqual(notebook.name, name)

        self.note_store.listNotebooks.return_value = [ttypes.Notebook(
            name=name + '*',
            guid=guid,
            serviceUpdated=1,
        )]

        self.sync.notebooks_remote()

        notebook = self.sq(Notebook).filter(
            Notebook.guid == guid,
        ).one()
        self.assertEqual(notebook.name, name + '*')

    def test_remote_tags(self):
        """Test syncing remote tags"""
        name = str(datetime.now())
        guid = 'guid'

        self.note_store.listTags = MagicMock()
        self.note_store.listTags.return_value = [ttypes.Tag(
            name=name,
            guid=guid,
        )]

        self.sync.tags_remote()
        tag = self.sq(Tag).filter(
            Tag.guid == guid,
        ).one()
        self.assertEqual(tag.name, name)

        self.note_store.listTags.return_value = [ttypes.Tag(
            name=name + '*',
            guid=guid,
        )]

        self.sync.tags_remote()
        tag = self.sq(Tag).filter(
            Tag.guid == guid,
        ).one()
        self.assertEqual(tag.name, name + '*')

    def test_remote_notes(self):
        """Test syncing remote notes"""
        remote = self._create_note()

        remote_notebook = ttypes.Notebook(
            name='default',
            defaultNotebook=True,
            guid='guid',
        )

        self.sync._note_store.getDefaultNotebook = MagicMock()
        self.sync._note_store.getDefaultNotebook.return_value = remote_notebook

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()

        self.assertEqual(note.title, remote.title)

        remote.title += '*'
        remote.updated = int(time.time() * 1000)

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        self.assertEqual(note.title, remote.title)

        self.sync._iter_all_notes = MagicMock()
        self.sync._iter_all_notes.return_value = []

        self.sync.notes_remote()
        with self.assertRaises(NoResultFound):
            # fetch synchronized not very genius, but we don't need that
            get_db_session().query(Note).filter(
                Note.guid == remote.guid,
            ).one()

    def test_remote_resources(self):
        """Test syncing remote resources"""
        remote = self._create_note(
            resources=[ttypes.Resource(
                data=ttypes.Data(
                    body=open(resource_path).read(),
                    bodyHash='',
                ),
                mime='image/png',
                attributes=ttypes.ResourceAttributes(
                    fileName='test.png',
                ),
            )],
        )

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        resource = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one().resources[0]
        self.assertEqual(
            'test.png', resource.file_name,
        )
        remote.resources = None

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        with self.assertRaises(NoResultFound):
            # fetch synchronized not very genius, but we don't need that
            get_db_session().query(Resource).filter(
                Resource.guid == resource.guid,
            ).one()

    def test_conflicts(self):
        """Test conflict situation syncing"""
        self.sync.note_store.createNote = MagicMock()
        self.sync.note_store.createNote.return_value.guid = 'guid'
        self.sync.note_store.updateNote = MagicMock()

        remote = self._create_note()

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()

        remote.updated = int(time.time() * 1000)
        remote.title += '*'

        self._mock_return_one_note(remote)

        note.title += '!'
        note.action = ACTION_CHANGE
        self.session.commit()

        self.sync.notes_remote()
        self.sync.notes_local()

        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        conflict = self.sq(Note).filter(
            Note.conflict_parent_id == note.id,
        ).one()
        self.assertEqual(conflict.action, ACTION_CONFLICT)
        self.assertEqual(note.title, 'test!')
        self.assertEqual(conflict.title, 'test*')

    def test_sync_with_unicode_place(self):
        """Test sync with unicode place from #186"""
        place_name = u"rasserie André"
        remote = self._create_note(
            attributes=ttypes.NoteAttributes(
                placeName=place_name.encode('utf8'),
            )
        )

        self._mock_return_one_note(remote)

        self.sync.notes_remote()
        self.assertTrue(
            self.sq(Place).filter(Place.name == place_name).count(),
        )

    def test_tag_notebook_validation(self):
        """Test tags and notebooks names validation for #201"""
        self.sync.note_store = get_note_store(TOKEN)

        notebook = Notebook(
            name="Blog posts%s" % str(datetime.now()), action=ACTION_CREATE,
        )
        self.session.add(notebook)
        self.session.commit()
        self.sync.notebooks_local()
        self.assertNotIn('skipped', self.sync.logs[-1])
        self.assertNotIn('Notebook.name', self.sync.logs[-1])
        tag = Tag(
            name="spackeria%s" % str(datetime.now()), action=ACTION_CREATE,
        )
        self.session.add(tag)
        self.session.commit()
        self.sync.tags_local()
        self.assertNotIn('skipped', self.sync.logs[-1])
        self.assertNotIn('Tag.name', self.sync.logs[-1])

    def test_share_note(self):
        """Test sharing note"""
        notebook = self._default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
            share_status=SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()

        self.sync.note_store.createNote = MagicMock()
        self.sync.note_store.createNote.return_value.guid = 'guid'

        self.note_store.shareNote = MagicMock()
        self.note_store.shareNote.return_value = '123'

        self.sync.notes_local()
        self.sync.notes_sharing()

        self.assertEqual(
            self.note_store.shareNote.call_args_list[0][0][1], 'guid',
        )
        self.assertEqual(note.share_status, SHARE_SHARED)

    def test_stop_sharing(self):
        """Test stop sharing"""
        self.sync.note_store = get_note_store(TOKEN)

        notebook = self._get_default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
            share_status=SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()
        self.sync.notes_local()
        self.sync.notes_sharing()
        note.share_status = SHARE_NEED_STOP
        self.session.commit()
        self.sync.notes_remote()
        self.sync.notes_stop_sharing()
        self.assertEqual(note.share_status, SHARE_NONE)

    def test_change_sharing(self):
        """Test change sharing"""
        self.sync.note_store = get_note_store(TOKEN)

        notebook = self._get_default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
            share_status=SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()
        self.sync.notes_local()
        share_url = self.sync._note_store.shareNote(self.auth_token, note.guid)
        self.sync.notes_remote()
        self.sync.notes_sharing()
        self.assertIn(share_url, note.share_url)
        self.assertEqual(note.share_status, SHARE_SHARED)
        self.note_store.stopSharingNote(self.auth_token, note.guid)
        self.sync.notes_remote()
        self.assertEqual(note.share_status, SHARE_NONE)

    def test_shard_id(self):
        """Test receiving shard id"""
        self.assertTrue(len(self.sync.shard_id) > 0)


class NotebookSyncCase(unittest.TestCase):
    """Test notebook sync"""

    def setUp(self):
        self._create_db_session()
        self._create_note_store()
        self._create_user_store()
        self._create_sync()

    def _create_db_session(self):
        """Create database session"""
        self.session = get_db_session()

    def _create_note_store(self):
        """Create note store mock"""
        self.note_store = MagicMock()

    def _create_user_store(self):
        """Create user store mock"""
        self.user_store = MagicMock()

    def _create_sync(self):
        """Create sync object"""
        self.token = 'token'
        self.sync = NotebookSync(
            self.token,
            self.session,
            self.note_store,
            self.user_store,
        )
        self.sync.app = MagicMock()

    def test_push_new_notebook(self):
        """Test push new notebook"""
        notebook = Notebook(
            name='name',
            action=ACTION_CREATE,
            stack='stack',
        )
        self.session.add(notebook)
        self.session.commit()

        guid = 'guid'
        self.note_store.createNotebook.return_value.guid = guid

        self.sync.push()
        pushed = self.note_store.createNotebook.call_args_list[0][0][1]

        self.assertEqual(pushed.name, notebook.name)
        self.assertEqual(pushed.stack, notebook.stack)

        self.assertEqual(notebook.guid, guid)

    def test_push_changed_notebook(self):
        """Test push changed notebook"""
        notebook = Notebook(
            name='name',
            action=ACTION_CHANGE,
            guid='guid',
        )
        self.session.add(notebook)
        self.session.commit()

        self.sync.push()
        pushed = self.note_store.updateNotebook.call_args_list[0][0][1]

        self.assertEqual(pushed.name, notebook.name)
        self.assertEqual(pushed.stack, notebook.stack)

    def _base_test_push_notebook_duplicates(self, action):
        """Base test push notebook duplicates"""
        notebook = Notebook(
            name='name',
            action=action,
        )
        self.session.add(notebook)

        original = Notebook(
            name='name',
            action=ACTION_NONE,
        )
        self.session.add(original)
        self.session.commit()

        note1 = Note(
            title='title',
            notebook=notebook,
        )
        note2 = Note(
            title='title',
            notebook=original,
        )
        self.session.add(note1)
        self.session.add(note2)

        self.sync.push()

        self.assertItemsEqual(
            self.session.query(Notebook).all(), [original],
        )
        self.assertEqual(self.session.query(Note).filter(
            Note.notebook == original
        ).count(), 2)

    def test_duplicates_on_push_new(self):
        """Test duplicates on pushing new notebook"""
        self.note_store.createNotebook.side_effect =\
            edam.error.ttypes.EDAMUserException
        self._base_test_push_notebook_duplicates(ACTION_CREATE)

    def test_duplicates_on_push_changed(self):
        """Test duplicates on pushing changed notebook"""
        self.note_store.updateNotebook.side_effect =\
            edam.error.ttypes.EDAMUserException
        self._base_test_push_notebook_duplicates(ACTION_CHANGE)
