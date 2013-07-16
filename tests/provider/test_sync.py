# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..',
))
# patch settings:
import settings

from settings import TOKEN
from everpad.provider.sync import note, notebook, tag
from everpad.provider.tools import get_db_session
from everpad.provider import models
from everpad import const
from evernote.edam.type import ttypes
from evernote import edam
from datetime import datetime
from mock import MagicMock
import unittest


resource_path = os.path.join(os.path.dirname(__file__), '../test.png')


class BaseSyncCase(unittest.TestCase):
    """Base sync case"""
    sync_cls = None

    def setUp(self):
        self._create_db_session()
        self._create_note_store()
        self._create_user_store()
        self._create_sync()

    def tearDown(self):
        self.session.flush()

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
    sync_cls = notebook.PushNotebook

    def test_push_new_notebook(self):
        """Test push new notebook"""
        notebook = models.Notebook(
            name='name',
            action=const.ACTION_CREATE,
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
        notebook = models.Notebook(
            name='name',
            action=const.ACTION_CHANGE,
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
        notebook = models.Notebook(
            name='name',
            action=action,
        )
        self.session.add(notebook)

        original = models.Notebook(
            name='name',
            action=const.ACTION_NONE,
        )
        self.session.add(original)
        self.session.commit()

        note1 = models.Note(
            title='title',
            notebook=notebook,
        )
        note2 = models.Note(
            title='title',
            notebook=original,
        )
        self.session.add(note1)
        self.session.add(note2)

        self.sync.push()

        self.assertItemsEqual(
            self.session.query(models.Notebook).all(), [original],
        )
        self.assertEqual(self.session.query(models.Note).filter(
            models.Note.notebook == original
        ).count(), 2)

    def test_duplicates_on_push_new(self):
        """Test duplicates on pushing new notebook"""
        self.note_store.createNotebook.side_effect =\
            edam.error.ttypes.EDAMUserException
        self._base_test_push_notebook_duplicates(const.ACTION_CREATE)

    def test_duplicates_on_push_changed(self):
        """Test duplicates on pushing changed notebook"""
        self.note_store.updateNotebook.side_effect =\
            edam.error.ttypes.EDAMUserException
        self._base_test_push_notebook_duplicates(const.ACTION_CHANGE)


class PullNotebookCase(BaseSyncCase):
    """Test notebook sync"""
    sync_cls = notebook.PullNotebook

    def test_pull_new_notebook(self):
        """Test pull new notebook"""
        notebook_name = 'name'

        self.note_store.listNotebooks.return_value = [
            ttypes.Notebook(name=notebook_name),
        ]

        self.sync.pull()

        notebook = self.session.query(models.Notebook).one()
        self.assertEqual(notebook.name, notebook_name)

    def test_pull_updated_notebook(self):
        """Test pull updated notebook"""
        guid = 'guid'
        notebook = models.Notebook(
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
        notebook = models.Notebook(
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
        notebook = models.Notebook(
            name='name',
            guid='guid',
            action=const.ACTION_NONE,
        )
        self.session.add(notebook)
        self.session.commit()

        self.note_store.listNotebooks.return_value = []

        self.sync.pull()

        self.assertEqual(self.session.query(models.Notebook).count(), 0)


class PushTagCase(BaseSyncCase):
    """Test tag sync"""
    sync_cls = tag.PushTag

    def test_push_new_tag(self):
        """Test push new tag"""
        guid = 'guid'
        tag = models.Tag(
            name='tag',
            action=const.ACTION_CREATE,
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
        tag = models.Tag(
            name='tag',
            action=const.ACTION_CHANGE,
        )
        self.session.add(tag)
        self.session.commit()

        self.sync.push()
        pushed = self.note_store.updateTag.call_args_list[0][0][1]

        self.assertEqual(pushed.name, tag.name)


class PullTagCase(BaseSyncCase):
    """Test tag sync"""
    sync_cls = tag.PullTag

    def test_pull_new_tag(self):
        """Test pull new tags"""
        tag_name = 'name'
        guid = 'guid'
        self.note_store.listTags.return_value = [ttypes.Tag(
            name=tag_name, guid=guid,
        )]

        self.sync.pull()
        tag = self.session.query(models.Tag).one()

        self.assertEqual(tag.name, tag_name)
        self.assertEqual(tag.guid, guid)

    def test_pull_changed_tag(self):
        """Test pull changed tags"""
        tag = models.Tag(
            name='name',
            guid='guid',
            action=const.ACTION_NONE,
        )
        self.session.add(tag)
        self.session.commit()

        tag_name = 'name*'
        self.note_store.listTags.return_value = [ttypes.Tag(
            name=tag_name, guid=tag.guid,
        )]

        self.sync.pull()
        self.assertEqual(tag.name, tag_name)

    def test_delete_after_pull(self):
        """Test delete non exists after pull"""
        tag = models.Tag(
            name='name',
            guid='guid',
            action=const.ACTION_NONE,
        )
        self.session.add(tag)
        self.session.commit()

        self.note_store.listTags.return_value = []
        self.sync.pull()

        self.assertEqual(self.session.query(models.Tag).count(), 0)


class PushNoteCase(BaseSyncCase):
    """Push note case"""
    sync_cls = note.PushNote

    def _create_resources(self, note):
        """Create resources"""
        resource_path = '/tmp/resource'
        with open(resource_path, 'w') as resource_file:
            resource_file.write('test')

        file_name = 'resource'

        resource = models.Resource(
            note_id=note.id,
            file_name=file_name,
            mime='plain/text',
            file_path=resource_path,
            action=const.ACTION_NONE,
        )
        self.session.add(resource)
        self.session.commit()

        return file_name

    def test_push_new_note(self):
        """Test push new note"""
        guid = 'guid'
        note = models.Note(
            title='note',
            content='content',
            action=const.ACTION_CREATE,
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
        note = models.Note(
            title='note',
            content='content',
            guid='guid',
            action=const.ACTION_CHANGE,
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
        note = models.Note(
            title='note',
            content='content',
            guid='guid',
            action=const.ACTION_DELETE,
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
        note = models.Note(
            title='note',
            content='content',
            action=const.ACTION_CREATE,
            share_status=const.SHARE_NEED_SHARE,
        )
        self.session.add(note)
        self.session.commit()

        self.note_store.createNote.return_value.guid = 'guid'
        self.sync.push()

        self.assertEqual(note.share_status, const.SHARE_SHARED)
        self.assertIsNotNone(note.share_url)

    def test_push_for_stop_sharing(self):
        """Test push for stop sharing"""
        note = models.Note(
            title='note',
            content='content',
            action=const.ACTION_CREATE,
            share_status=const.SHARE_NEED_STOP,
        )
        self.session.add(note)
        self.session.commit()

        self.note_store.createNote.return_value.guid = 'guid'
        self.sync.push()

        self.assertEqual(note.share_status, const.SHARE_NONE)


class PullNoteCase(BaseSyncCase):
    """Pull note case"""
    sync_cls = note.PullNote

    def setUp(self):
        super(PullNoteCase, self).setUp()
        self._create_default_notebook()

    def _create_default_notebook(self):
        """Create default notebook"""
        self.notebook = models.Notebook(
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

        note = self.session.query(models.Note).one()

        self.assertEqual(note.guid, note_guid)
        self.assertEqual(note.title, note_title)
        self.assertEqual(self.session.query(models.Resource).count(), 1)

    def test_pull_changed_note(self):
        """Test pull changed note"""
        note_guid = 'guid'
        note_title = 'title'
        note = models.Note(
            title='note',
            guid=note_guid,
            updated=0,
        )
        self.session.add(note)
        self.session.commit()

        self._create_remote_note(note_title, note_guid)

        self.sync.pull()

        self.assertEqual(note.title, note_title)
        self.assertEqual(self.session.query(models.Resource).count(), 1)

    def test_delete_after_pull(self):
        """Test delete non exists note after pull"""
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        search_result = MagicMock()
        search_result.totalNotes = 0
        search_result.startIndex = 0
        search_result.notes = []
        self.note_store.findNotes.return_value = search_result

        self.sync.pull()

        self.assertEqual(self.session.query(models.Note).count(), 0)

    def test_pull_with_conflict(self):
        """Test pull with conflict"""
        note_guid = 'guid'
        note_title = 'title'
        note = models.Note(
            title='note',
            guid=note_guid,
            updated=0,
            action=const.ACTION_CHANGE,
        )
        self.session.add(note)
        self.session.commit()

        self._create_remote_note(note_title, note_guid)

        self.sync.pull()

        self.assertEqual(self.session.query(models.Note).filter(
            models.Note.action == const.ACTION_CONFLICT
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

        local_note = self.session.query(models.Note).one()

        self.assertEqual(local_note.share_status, const.SHARE_SHARED)

    def test_pull_not_shared(self):
        """Test pull not shared note"""
        note_guid = 'guid'
        note_title = 'title'

        note = models.Note(
            title=note_title,
            guid=note_guid,
            updated=0,
            action=const.ACTION_NONE,
            share_status=const.SHARE_SHARED,
        )
        self.session.add(note)
        self.session.commit()

        note = self._create_remote_note(note_title, note_guid)
        note.attributes.shareDate = None

        self.sync.pull()

        local_note = self.session.query(models.Note).one()

        self.assertEqual(local_note.share_status, const.SHARE_NONE)
