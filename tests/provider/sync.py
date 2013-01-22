# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')
from settings import TOKEN
from everpad.const import HOST
from everpad.provider.sync import SyncAgent
from everpad.provider.tools import get_db_session, get_note_store
from everpad.provider.models import (
    Note, Notebook, Place, Tag, Resource, ACTION_CREATE,
    ACTION_CHANGE, ACTION_NONE, ACTION_DELETE, ACTION_CONFLICT,
    SHARE_NONE, SHARE_NEED_SHARE, SHARE_SHARED, SHARE_NEED_STOP,
)
from evernote.edam.type import ttypes
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
import unittest
import os
import time


note_store = get_note_store(TOKEN)  # prevent reconecting
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
        self.note_store = note_store
        if self._need_to_update():
            self.need_to_update = True
        else:
            self.need_to_update = False

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

    def _get_default_notebook(self):
        """Get default notebook"""
        remote_notebook = self.note_store.getDefaultNotebook(self.auth_token)
        notebook = Notebook(guid=remote_notebook.guid)
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()
        return notebook

    def test_local_notebooks(self):
        """Test sync local notebooks"""
        name = str(datetime.now())
        notebook = Notebook(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(notebook)
        self.session.commit()
        self.sync.notebooks_local()
        self.assertEqual(notebook.action, ACTION_NONE)
        notebook_remote = self.note_store.getNotebook(self.auth_token, notebook.guid)
        self.assertEqual(notebook.name, notebook_remote.name)
        notebook.name += '*'
        notebook.action = ACTION_CHANGE
        self.sync.notebooks_local()
        self.assertEqual(notebook.action, ACTION_NONE)
        notebook_remote = self.note_store.getNotebook(self.auth_token, notebook.guid)
        self.assertEqual(notebook.name, notebook_remote.name)

    def test_local_tags(self):
        """Test sync local tags"""
        name = str(datetime.now())
        tag = Tag(
            name=name, action=ACTION_CREATE,
        )
        self.session.add(tag)
        self.session.commit()
        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)
        tag_remote = self.note_store.getTag(self.auth_token, tag.guid)
        self.assertEqual(tag.name, tag_remote.name)
        tag.name += '*'
        tag.action = ACTION_CHANGE
        self.sync.tags_local()
        self.assertEqual(tag.action, ACTION_NONE)
        tag_remote = self.note_store.getTag(self.auth_token, tag.guid)
        self.assertEqual(tag.name, tag_remote.name)

    def test_local_notes(self):
        """Test local notes sync"""
        notebook = self._get_default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
        )
        self.session.add(note)
        self.session.commit()
        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertEqual(notebook.guid, note_remote.notebookGuid)
        note.title += '*'
        note.action = ACTION_CHANGE
        self.sync.notes_local()
        self.assertEqual(note.action, ACTION_NONE)
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertEqual(note.title, note_remote.title)
        note.action = ACTION_DELETE
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, False, False, False,
        )
        self.assertFalse(note_remote.active)
        with self.assertRaises(NoResultFound):
            self.sq(Note).filter(
                Note.guid == note_remote.guid,
            ).one()

    def test_local_resources(self):
        """Test local resources"""
        remote_notebook = self.note_store.getDefaultNotebook(self.auth_token)
        notebook = Notebook(guid=remote_notebook.guid)
        notebook.from_api(remote_notebook)
        self.session.add(notebook)
        self.session.commit()
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
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, True, False, False,
        )
        self.assertEqual('test.png', note_remote.resources[0].attributes.fileName)
        self.session.delete(res)
        self.session.commit()
        note.action = ACTION_CHANGE
        self.sync.notes_local()
        note_remote = self.note_store.getNote(
            self.auth_token, note.guid, True, True, False, False,
        )
        self.assertIsNone(note_remote.resources)

    def test_remote_notebooks(self):
        """Test syncing remote notebooks"""
        name = str(datetime.now())
        remote = self.note_store.createNotebook(
            self.auth_token, ttypes.Notebook(
                name=name,
            ),
        )
        self.sync.notebooks_remote()
        notebook = self.sq(Notebook).filter(
            Notebook.guid == remote.guid,
        ).one()
        self.assertEqual(notebook.name, name)
        remote.name += '*'
        self.note_store.updateNotebook(
            self.auth_token, remote,
        )
        self.sync.notebooks_remote()
        notebook = self.sq(Notebook).filter(
            Notebook.guid == remote.guid,
        ).one()
        self.assertEqual(notebook.name, name + '*')

    def test_remote_tags(self):
        """Test syncing remote tags"""
        name = str(datetime.now())
        remote = self.note_store.createTag(
            self.auth_token, ttypes.Tag(
                name=name,
            ),
        )
        self.sync.tags_remote()
        tag = self.sq(Tag).filter(
            Tag.guid == remote.guid,
        ).one()
        self.assertEqual(tag.name, name)
        remote.name += '*'
        self.note_store.updateTag(
            self.auth_token, remote,
        )
        self.sync.tags_remote()
        tag = self.sq(Tag).filter(
            Tag.guid == remote.guid,
        ).one()
        self.assertEqual(tag.name, name + '*')

    def test_remote_notes(self):
        """Test syncing remote notes"""
        remote = self._create_remote_note()
        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        self.assertEqual(note.title, remote.title)
        remote.title += '*'
        remote.updated = int(time.time() * 1000)
        self.note_store.updateNote(self.auth_token, remote)
        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        self.assertEqual(note.title, remote.title)
        self.note_store.deleteNote(self.auth_token, note.guid)
        self.sync.notes_remote()
        with self.assertRaises(NoResultFound):
            # fetch synchronized not very genius, but we don't need that
            get_db_session().query(Note).filter(
                Note.guid == remote.guid,
            ).one()

    def test_remote_resources(self):
        """Test syncing remote resources"""
        remote = self._create_remote_note(
            resources=[ttypes.Resource(
                data=ttypes.Data(body=open(resource_path).read()),
                mime='image/png',
                attributes=ttypes.ResourceAttributes(
                    fileName='test.png',
                )
            )],
        )
        self.sync.notes_remote()
        resource = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one().resources[0]
        self.assertEqual(
            'test.png', resource.file_name,
        )
        remote.resources = None
        self.note_store.updateNote(self.auth_token, remote)
        self.sync.notes_remote()
        with self.assertRaises(NoResultFound):
            # fetch synchronized not very genius, but we don't need that
            get_db_session().query(Resource).filter(
                Resource.guid == resource.guid,
            ).one()

    def test_conflicts(self):
        """Test conflict situation syncing"""
        remote = self._create_remote_note()
        self.sync.notes_remote()
        note = self.sq(Note).filter(
            Note.guid == remote.guid,
        ).one()
        remote.updated = int(time.time() * 1000)
        remote.title += '*'
        self.note_store.updateNote(self.auth_token, remote)
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
        self._create_remote_note(
            attributes=ttypes.NoteAttributes(
                placeName=place_name.encode('utf8'),
            )
        )
        self.sync.notes_remote()
        self.assertTrue(
            self.sq(Place).filter(Place.name == place_name).count(),
        )

    def test_tag_notebook_validation(self):
        """Test tags and notebooks names validation for #201"""
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
        share_url = self.note_store.shareNote(self.auth_token, note.guid)
        self.assertEqual(note.share_url, share_url)
        self.assertEqual(note.share_status, SHARE_SHARED)

    def test_stop_sharing(self):
        """Test stop sharing"""
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
        self.sync.notes_stop_sharing()
        self.assertEqual(note.share_status, SHARE_NONE)

    def test_change_sharing(self):
        """Test change sharing"""
        notebook = self._get_default_notebook()
        note = Note(
            title='67890', action=ACTION_CREATE,
            notebook=notebook, content='12345',
            share_status=SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()
        self.sync.notes_local()
        share_url = self.note_store.shareNote(self.auth_token, note.guid)
        self.sync.notes_remote()
        self.assertEqual(note.share_url, share_url)
        self.assertEqual(note.share_status, SHARE_SHARED)
        self.note_store.stopSharingNote(self.auth_token, note.guid)
        self.sync.notes_remote()
        self.assertEqual(note.share_status, SHARE_NONE)

    def test_shar_id(self):
        """Test receiving shard id"""
        self.assertTrue(len(self.sync.shard_id) > 0)


if __name__ == '__main__':
    unittest.main()
