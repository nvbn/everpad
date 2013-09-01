# -*- coding: utf-8 -*-
from .. import settings

from dbus.exceptions import DBusException
from mock import MagicMock
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad import const
from everpad.provider import models
import unittest
import dbus
import everpad.basetypes as btype
from .. import factories


class FindTestCase(unittest.TestCase):
    """Find notes method test case"""

    def setUp(self):
        self._create_service()
        self._create_notebooks()
        self._create_notes()

    def _create_notes(self):
        """Create notes"""
        notes = [
            self.service.create_note(btype.Note(
                title='New note',
                content="New note content",
                tags=['ab', 'cd'],
                notebook=self.notebook.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place='first',
                pinnded=False,
            ).struct),
            self.service.create_note(btype.Note(
                title='Old note',
                content="Old note content",
                tags=['ef', 'gh'],
                notebook=self.notebook2.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place='second',
                pinnded=False,
            ).struct),
            self.service.create_note(btype.Note(
                title='not',
                content="oke",
                tags=['ab', 'gh'],
                notebook=self.notebook.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place='second',
                pinnded=True,
            ).struct),
            self.service.create_note(btype.Note(
                title=u'Заметка',
                content=u"Заметка",
                tags=[u'тэг'],
                notebook=self.notebook.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place=u'место',
                pinnded=False,
            ).struct),
            self.service.create_note(btype.Note(
                title=u'заметка',
                content=u"заметка",
                tags=[u'тэг'],
                notebook=self.notebook.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place=u'место',
                pinnded=False,
            ).struct),
        ]
        self.notes = btype.Note.list << [
            self.service.update_note(note) for note in notes
        ]

    def _create_notebooks(self):
        """Create notebooks"""
        self.notebook =\
            btype.Notebook << self.service.create_notebook('test', None)
        self.notebook2 =\
            btype.Notebook << self.service.create_notebook('test2', None)
        self.notebook3 =\
            btype.Notebook << self.service.create_notebook(u'Блокнот', None)

    def _create_service(self):
        """Create service"""
        self.service = ProviderService()
        self.service._session = get_db_session()
        models.Note.session = self.service._session  # TODO: fix that shit

    def _to_ids(self, items):
        return set(map(lambda item: item.id, items))

    def _find(self, *args, **kwargs):
        return btype.Note.list << self.service.find_notes(*args, **kwargs)

    def test_by_words(self):
        """Test notes find by words"""
        all_notes = self._find(
            'not', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(all_notes), self._to_ids(self.notes[:-2]),
        )
        two = self._find(
            'note', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(two), self._to_ids(self.notes[:2]),
        )
        blank = self._find(
            'not note', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(len(blank), 0)

    def test_by_tags(self):
        """Test note find by tags"""
        tags = btype.Tag.list << self.service.list_tags()
        first_last = self._find(
            '', dbus.Array([], signature='i'),
            [tags[0].id], 0, 100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(first_last), [self.notes[0].id, self.notes[2].id],
        )
        second = self._find(
            '', dbus.Array([], signature='i'),
            [tags[2].id], 0, 100,
            const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(second), [self.notes[1].id],
        )
        all_notes = self._find(
            '', dbus.Array([], signature='i'),
            map(lambda tag: tag.id, tags), 0, 100,
            const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(all_notes), self._to_ids(self.notes),
        )

    def test_by_notebooks(self):
        """Test find note by notebooks"""
        all_notebooks = self._find(
            '', self._to_ids([self.notebook, self.notebook2]),
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(all_notebooks), self._to_ids(self.notes),
        )
        second = self._find(
            '', [self.notebook2.id],
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(second), [self.notes[1].id],
        )

    def test_combine(self):
        """Test find by combination"""
        places = btype.Place.list << self.service.list_places()
        tags = btype.Tag.list << self.service.list_tags()
        first = self._find(
            'new', [self.notebook.id], [tags[0].id], places[0].id,
            100, const.ORDER_UPDATED_DESC, False,
        )
        self.assertItemsEqual(
            self._to_ids(first), [self.notes[0].id],
        )
        last = self._find(
            'oke', [self.notebook.id], [tags[0].id], places[1].id,
            100, const.ORDER_UPDATED_DESC, True,
        )
        self.assertItemsEqual(
            self._to_ids(last), [self.notes[2].id],
        )

    def test_unicode_ignorecase(self):
        """Test unicode ignorecase"""
        all_notes = self._find(
            u'заметка', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, const.ORDER_UPDATED_DESC, -1,
        )
        self.assertItemsEqual(
            self._to_ids(all_notes), self._to_ids(self.notes[-2:]),
        )


class MethodsCase(unittest.TestCase):
    """Case for dbus shortcuts"""

    def setUp(self):
        self.service = ProviderService()
        self.session = get_db_session()
        self.service._session = self.session
        models.Note.session = self.session
        self.service.qobject = MagicMock()
        self.service.app = MagicMock()
        self.service.sync = MagicMock()
        factories.invoke_session(self.session)

    def tearDown(self):
        self.session.flush()

    def _create_note(self, **kwargs):
        """Create note"""
        note = factories.NoteFactory.create(
            action=const.ACTION_NONE,
            **kwargs
        )
        self.session.commit()
        return note

    def test_get_note(self):
        """Test get note method"""
        note = self._create_note()
        remote_note = btype.Note << self.service.get_note(note.id)
        self.assertEqual(remote_note.title, note.title)

    def test_get_note_by_guid(self):
        """Test get note method"""
        note = self._create_note(guid='guid')
        remote_note = btype.Note << self.service.get_note_by_guid(note.guid)
        self.assertEqual(remote_note.title, note.title)

    def test_get_note_alternatives(self):
        """Test get note alternatives"""
        note = self._create_note(guid='guid')
        alternative = factories.NoteFactory.create(
            guid='guid',
            action=const.ACTION_CONFLICT,
            conflict_parent_id=note.id,
        )
        self.session.commit()
        remote_notes = btype.Note.list << self.service.get_note_alternatives(
            note.id,
        )
        self.assertEqual(remote_notes[0].id, alternative.id)

    def test_list_notebooks(self):
        """Test list notebooks method"""
        notebooks = factories.NotebookFactory.create_batch(
            10, action=const.ACTION_NONE,
        )
        self.session.commit()
        notebooks = [notebook.id for notebook in notebooks]

        remote_notebooks = btype.Notebook.list << self.service.list_notebooks()
        ids = [notebook.id for notebook in remote_notebooks]

        self.assertItemsEqual(notebooks, ids)

    def test_get_notebook(self):
        """Test get notebook method"""
        notebook = factories.NotebookFactory.create(
            action=const.ACTION_NONE,
        )
        deleted_notebook = factories.NotebookFactory(
            action=const.ACTION_DELETE,
        )
        self.session.commit()

        remote_notebook = btype.Notebook << self.service.get_notebook(
            notebook.id,
        )
        self.assertEqual(notebook.name, remote_notebook.name)

        with self.assertRaises(DBusException):
            self.service.get_notebook(
                deleted_notebook.id,
            )

    def test_get_notebook_notes_count(self):
        """Test get notebook notes count method"""
        notebook = factories.NotebookFactory.create(
            action=const.ACTION_NONE,
        )
        factories.NoteFactory.create_batch(
            10, action=const.ACTION_NONE,
            notebook=notebook,
        )
        self.session.commit()
        self.assertEqual(
            self.service.get_notebook_notes_count(notebook.id), 10,
        )

    def test_update_notebook(self):
        """Test update notebook method"""
        notebook = factories.NotebookFactory.create(
            action=const.ACTION_NONE,
        )
        self.session.commit()
        new_name = 'name'
        notebook_btype = btype.Notebook.from_obj(notebook)
        notebook_btype.name = new_name
        notebook_btype = btype.Notebook << self.service.update_notebook(
            notebook_btype.struct,
        )
        self.assertEqual(notebook_btype.name, new_name)
        self.assertEqual(notebook.name, new_name)

    def test_delete_notebook(self):
        """Test delete notebook"""
        notebook = factories.NotebookFactory.create(
            name='notebook',
            action=const.ACTION_NONE,
        )
        self.session.commit()
        self.service.delete_notebook(notebook.id)
        self.assertEqual(notebook.action, const.ACTION_DELETE)

    def test_list_tags(self):
        """Test list tags"""
        tags = factories.TagFactory.create_batch(
            10, action=const.ACTION_NONE,
        )
        self.session.commit()
        tags = [tag.id for tag in tags]
        remote_tags = btype.Tag.list << self.service.list_tags()
        tags_ids = [tag.id for tag in remote_tags]
        self.assertItemsEqual(tags_ids, tags)

    def test_get_tag_notes_count(self):
        """Test get tag notes count method"""
        tag = factories.TagFactory.create(
            action=const.ACTION_NONE,
        )
        factories.NoteFactory.create_batch(
            10, action=const.ACTION_NONE,
            tags=[tag],
        )
        self.session.commit()
        self.assertEqual(
            self.service.get_tag_notes_count(tag.id), 10,
        )

    def test_delete_tag(self):
        """Test delete tag"""
        tag = factories.TagFactory.create(
            action=const.ACTION_NONE,
        )
        self.session.commit()
        self.service.delete_tag(tag.id)
        self.assertEqual(tag.action, const.ACTION_DELETE)

    def test_update_tag(self):
        """Test update tag method"""
        tag = factories.TagFactory.create(
            action=const.ACTION_NONE,
        )
        self.session.commit()
        new_name = 'name'
        tag_btype = btype.Tag.from_obj(tag)
        tag_btype.name = new_name
        tag_btype = btype.Tag << self.service.update_tag(
            tag_btype.struct,
        )
        self.assertEqual(tag_btype.name, new_name)
        self.assertEqual(tag.name, new_name)

    def test_create_note(self):
        """Test create note"""
        notebook = factories.NotebookFactory.create(default=True)
        self.session.commit()

        title = 'note'
        note_btype = btype.Note(
            title=title,
            tags=[],
            id=const.NONE_ID,
            notebook=notebook.id,
        )

        note_btype = btype.Note << self.service.create_note(
            btype.Note >> note_btype,
        )
        note = self.session.query(models.Note).filter(
            models.Note.id == note_btype.id,
        ).one()

        self.assertEqual(note_btype.title, title)
        self.assertEqual(note.title, title)

    def test_update_note(self):
        """Test update note"""
        notebook = factories.NotebookFactory.create(default=True)
        self.session.commit()

        note = self._create_note(
            notebook_id=notebook.id,
        )

        new_title = 'title'

        note_btype = btype.Note.from_obj(note)
        note_btype.title = new_title

        note_btype = btype.Note << self.service.update_note(
            note_btype.struct,
        )
        note = self.session.query(models.Note).filter(
            models.Note.id == note_btype.id,
        ).one()

        self.assertEqual(note_btype.title, new_title)
        self.assertEqual(note.title, new_title)

    def test_get_note_resources(self):
        """Test get note resources"""
        note = self._create_note()

        resource = factories.ResourceFactory.create(
            file_name='name',
            action=const.ACTION_NONE,
            note_id=note.id,
        )
        self.session.commit()

        resources_btype = btype.Resource.list << self.service.get_note_resources(
            note.id,
        )

        self.assertEqual(resources_btype[0].file_name, resource.file_name)

    def test_update_note_resources(self):
        """Test update note resources"""
        note = self._create_note()

        resource = btype.Resource(
            file_name='test',
        )

        self.service.update_note_resources(
            note.id, btype.Resource.list >> [resource],
        )

        resource = self.session.query(models.Resource).one()
        self.assertEqual(resource.file_name, 'test')

    def test_delete_note(self):
        """Test delete note"""
        note = self._create_note()

        self.service.delete_note(note.id)

        self.assertEqual(note.action, const.ACTION_DELETE)

    def test_create_notebook(self):
        """Test create notebook"""
        notebook_btype =\
            btype.Notebook << self.service.create_notebook('test', 'test')

        notebook = self.session.query(models.Notebook).filter(
            models.Notebook.id == notebook_btype.id,
        ).one()
        self.assertEqual(notebook.name, 'test')

    def test_authenticate(self):
        """Test authenticate"""
        self.service.authenticate('test')
        self.service.qobject\
            .remove_authenticate_signal.emit.assert_called_once_with()
        self.service.qobject\
            .authenticate_signal.emit.assert_called_once_with('test')

    def test_remove_authentication(self):
        """Test remove authentication"""
        self.service.remove_authentication()
        self.service.qobject\
            .remove_authenticate_signal.emit.assert_called_once_with()

    def test_list_places(self):
        """Test list places"""
        places = factories.PlaceFactory.create_batch(10)
        self.session.commit()
        place_ids = [place.id for place in places]
        places_btype = btype.Place.list << self.service.list_places()
        for place_btype in places_btype:
            self.assertIn(place_btype.id, place_ids)

    def test_share_note(self):
        """Test share note"""
        note = self._create_note()

        self.service.share_note(note.id)
        self.assertEqual(note.share_status, const.SHARE_NEED_SHARE)
        self.service.sync.assert_called_once_with()

    def test_stop_sharing_note(self):
        """Test stop sharing note"""
        note = self._create_note(share_status=const.SHARE_SHARED)

        self.service.stop_sharing_note(note.id)
        self.assertEqual(note.share_status, const.SHARE_NEED_STOP)
        self.service.sync.assert_called_once_with()

    def test_is_first_synced(self):
        """Test is first synced"""
        self.assertFalse(self.service.is_first_synced())
