# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')
from settings import TOKEN
from everpad.const import HOST
from everpad.provider.sync import (
    SyncAgent, PushNotebook, PullNotebook, PushTag, PullTag, PushNote,
    PullNote,
)
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


class BaseSyncCase(unittest.TestCase):
    """Base sync case"""
    sync_cls = None

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
        self.sync = self.sync_cls(
            self.token,
            self.session,
            self.note_store,
            self.user_store,
        )
        self.sync.app = MagicMock()


class PushNotebookCase(BaseSyncCase):
    """Test notebook sync"""
    sync_cls = PushNotebook

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


class PullNotebookCase(BaseSyncCase):
    """Test notebook sync"""
    sync_cls = PullNotebook

    def test_pull_new_notebook(self):
        """Test pull new notebook"""
        notebook_name = 'name'

        self.note_store.listNotebooks.return_value = [
            ttypes.Notebook(name=notebook_name),
        ]

        self.sync.pull()

        notebook = self.session.query(Notebook).one()
        self.assertEqual(notebook.name, notebook_name)

    def test_pull_updated_notebook(self):
        """Test pull updated notebook"""
        guid = 'guid'
        notebook = Notebook(
            name='name',
            service_updated=0,
            guid=guid,
        )
        self.session.add(notebook)
        self.session.commit()

        notebook_name = 'name*'

        self.note_store.listNotebooks.return_value = [ttypes.Notebook(
            name=notebook_name, guid=guid, serviceUpdated=1,
        )]

        self.sync.pull()

        self.assertEqual(notebook.name, notebook_name)

    def test_pull_not_updated_notebook(self):
        """Test pull not updated notebook"""
        guid = 'guid'
        notebook = Notebook(
            name='name',
            service_updated=2,
            guid=guid,
        )
        self.session.add(notebook)
        self.session.commit()

        notebook_name = 'name*'

        self.note_store.listNotebooks.return_value = [ttypes.Notebook(
            name=notebook_name, guid=guid, serviceUpdated=1,
        )]

        self.sync.pull()

        self.assertNotEqual(notebook.name, notebook_name)

    def test_delete_after_pull(self):
        """Test delete notebooks after pull"""
        notebook = Notebook(
            name='name',
            guid='guid',
            action=ACTION_NONE,
        )
        self.session.add(notebook)
        self.session.commit()

        self.note_store.listNotebooks.return_value = []

        self.sync.pull()

        self.assertEqual(self.session.query(Notebook).count(), 0)


class PushTagCase(BaseSyncCase):
    """Test tag sync"""
    sync_cls = PushTag

    def test_push_new_tag(self):
        """Test push new tag"""
        guid = 'guid'
        tag = Tag(
            name='tag',
            action=ACTION_CREATE,
        )
        self.session.add(tag)
        self.session.commit()

        self.note_store.createTag.return_value.guid = guid
        self.sync.push()

        self.assertEqual(tag.guid, guid)
        self.assertEqual(
            self.note_store.createTag.call_args_list[0][0][1].name,
            tag.name,
        )

    def test_push_changed_tag(self):
        """Test push changed tag"""
        tag = Tag(
            name='tag',
            action=ACTION_CHANGE,
        )
        self.session.add(tag)
        self.session.commit()

        self.sync.push()
        pushed = self.note_store.updateTag.call_args_list[0][0][1]

        self.assertEqual(pushed.name, tag.name)


class PullTagCase(BaseSyncCase):
    """Test tag sync"""
    sync_cls = PullTag

    def test_pull_new_tag(self):
        """Test pull new tags"""
        tag_name = 'name'
        guid = 'guid'
        self.note_store.listTags.return_value = [Tag(
            name=tag_name, guid=guid,
        )]

        self.sync.pull()
        tag = self.session.query(Tag).one()

        self.assertEqual(tag.name, tag_name)
        self.assertEqual(tag.guid, guid)

    def test_pull_changed_tag(self):
        """Test pull changed tags"""
        tag = Tag(
            name='name',
            guid='guid',
            action=ACTION_NONE,
        )
        self.session.add(tag)
        self.session.commit()

        tag_name = 'name*'
        self.note_store.listTags.return_value = [Tag(
            name=tag_name, guid=tag.guid,
        )]

        self.sync.pull()
        self.assertEqual(tag.name, tag_name)

    def test_delete_after_pull(self):
        """Test delete non exists after pull"""
        tag = Tag(
            name='name',
            guid='guid',
            action=ACTION_NONE,
        )
        self.session.add(tag)
        self.session.commit()

        self.note_store.listTags.return_value = []
        self.sync.pull()

        self.assertEqual(self.session.query(Tag).count(), 0)


class PushNoteCase(BaseSyncCase):
    """Push note case"""
    sync_cls = PushNote

    def _create_resources(self, note):
        """Create resources"""
        resource_path = '/tmp/resource'
        with open(resource_path, 'w') as resource_file:
            resource_file.write('test')

        file_name = 'resource'

        resource = Resource(
            note_id=note.id,
            file_name=file_name,
            mime='plain/text',
            file_path=resource_path,
            action=ACTION_NONE,
        )
        self.session.add(resource)
        self.session.commit()

        return file_name

    def test_push_new_note(self):
        """Test push new note"""
        guid = 'guid'
        note = Note(
            title='note',
            content='content',
            action=ACTION_CREATE,
        )
        self.session.add(note)
        self.session.commit()

        file_name = self._create_resources(note)

        self.note_store.createNote.return_value.guid = guid
        self.sync.push()

        self.assertEqual(note.guid, guid)

        pushed = self.note_store.createNote.call_args_list[0][0][1]

        self.assertEqual(pushed.title, note.title)
        self.assertEqual(pushed.resources[0].attributes.fileName, file_name)

    def test_push_changed_note(self):
        """Test push changed note"""
        note = Note(
            title='note',
            content='content',
            guid='guid',
            action=ACTION_CHANGE,
        )
        self.session.add(note)
        self.session.commit()

        file_name = self._create_resources(note)

        self.sync.push()

        pushed = self.note_store.updateNote.call_args_list[0][0][1]

        self.assertEqual(pushed.title, note.title)
        self.assertEqual(pushed.resources[0].attributes.fileName, file_name)

    def test_delete_note(self):
        """Test delete note"""
        note = Note(
            title='note',
            content='content',
            guid='guid',
            action=ACTION_DELETE,
        )
        self.session.add(note)
        self.session.commit()

        self.sync.push()

        self.assertEqual(
            self.note_store.deleteNote.call_args_list[0][0][1],
            note.guid,
        )

    def test_push_for_sharing(self):
        """Test push for sharing"""
        note = Note(
            title='note',
            content='content',
            action=ACTION_CREATE,
            share_status=SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()

        self.note_store.createNote.return_value.guid = 'guid'
        self.sync.push()

        self.assertEqual(note.share_status, SHARE_SHARED)
        self.assertIsNotNone(note.share_url)

    def test_push_for_non_sharing(self):
        """Test push for non sharing"""
        note = Note(
            title='note',
            content='content',
            action=ACTION_CREATE,
            share_status=SHARE_NEED_STOP,
        )
        self.session.add(note)
        self.session.commit()

        self.note_store.createNote.return_value.guid = 'guid'
        self.sync.push()

        self.assertEqual(note.share_status, SHARE_NONE)


class PullNoteCase(BaseSyncCase):
    """Pull note case"""
    sync_cls = PullNote

    def setUp(self):
        super(PullNoteCase, self).setUp()
        self._create_default_notebook()

    def _create_default_notebook(self):
        """Create default notebook"""
        self.notebook = Notebook(
            guid='guid',
            name='name',
            default=True,
        )
        self.session.add(self.notebook)
        self.session.commit()

    def _create_remote_note(self, note_title, note_guid):
        """Create remote note"""
        remote_note = ttypes.Note(
            title=note_title,
            guid=note_guid,
            content='<en-note></en-note>',
            notebookGuid=self.notebook.guid,
            attributes=ttypes.NoteAttributes(),
            updated=1,
            resources=[ttypes.Resource(
                guid='file',
                mime='text',
                attributes=ttypes.ResourceAttributes(
                    fileName='file',
                ),
                data=ttypes.Data(
                    body='',
                    bodyHash='',
                ),
            )],
        )

        search_result = MagicMock()
        search_result.totalNotes = 1
        search_result.startIndex = 0
        search_result.notes = [remote_note]
        self.note_store.findNotes.return_value = search_result
        self.note_store.getNote.return_value = remote_note

        return remote_note

    def test_pull_new_note(self):
        """Test pull new note"""
        note_title = 'title'
        note_guid = 'guid'
        self._create_remote_note(note_title, note_guid)

        self.sync.pull()

        note = self.session.query(Note).one()

        self.assertEqual(note.guid, note_guid)
        self.assertEqual(note.title, note_title)
        self.assertEqual(self.session.query(Resource).count(), 1)

    def test_pull_changed_note(self):
        """Test pull changed note"""
        note_guid = 'guid'
        note_title = 'title'
        note = Note(
            title='note',
            guid=note_guid,
            updated=0,
        )
        self.session.add(note)
        self.session.commit()

        self._create_remote_note(note_title, note_guid)

        self.sync.pull()

        self.assertEqual(note.title, note_title)
        self.assertEqual(self.session.query(Resource).count(), 1)

    def test_delete_after_pull(self):
        """Test delete non exists note after pull"""
        note = Note(
            title='note',
            action=ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        search_result = MagicMock()
        search_result.totalNotes = 0
        search_result.startIndex = 0
        search_result.notes = []
        self.note_store.findNotes.return_value = search_result

        self.sync.pull()

        self.assertEqual(self.session.query(Note).count(), 0)

    def test_pull_with_conflict(self):
        """Test pull with conflict"""
        note_guid = 'guid'
        note_title = 'title'
        note = Note(
            title='note',
            guid=note_guid,
            updated=0,
            action=ACTION_CHANGE,
        )
        self.session.add(note)
        self.session.commit()

        self._create_remote_note(note_title, note_guid)

        self.sync.pull()

        self.assertEqual(self.session.query(Note).filter(
            Note.action == ACTION_CONFLICT
        ).count(), 1)

    def test_pull_shared(self):
        """Test pull shared note"""
        note_guid = 'guid'
        note_title = 'title'

        note = self._create_remote_note(note_title, note_guid)
        note.attributes.shareDate = 1

        self.note_store.shareNote = MagicMock()
        self.note_store.shareNote.return_value = 'url'

        self.sync.pull()

        local_note = self.session.query(Note).one()

        self.assertEqual(local_note.share_status, SHARE_SHARED)

    def test_pull_not_shared(self):
        """Test pull not shared note"""
        note_guid = 'guid'
        note_title = 'title'

        note = Note(
            title=note_title,
            guid=note_guid,
            updated=0,
            action=ACTION_NONE,
            share_status=SHARE_SHARED,
        )
        self.session.add(note)
        self.session.commit()

        note = self._create_remote_note(note_title, note_guid)
        note.attributes.shareDate = None

        self.sync.pull()

        local_note = self.session.query(Note).one()

        self.assertEqual(local_note.share_status, SHARE_NONE)
