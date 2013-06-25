# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')
# patch settings:
import settings

from dbus.exceptions import DBusException
from mock import MagicMock
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import (
    Note, Notebook, Tag, Resource, Place,
)
from everpad import const
from everpad.provider import models, tools
import unittest
import dbus
import everpad.basetypes as btype


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ProviderService()
        self.service._session = get_db_session()
        models.Note.session = self.service._session  # TODO: fix that shit
        self.session = self.service._session

    def _to_ids(self, items):
        return set(map(lambda item: item.id, items))

    def test_notebooks(self):
        """Test notebooks"""
        notebooks = []
        for i in range(100):
            notebooks.append(Notebook.from_tuple(
                self.service.create_notebook(str(i), None),
            ))
            self.assertEqual(notebooks[-1].name, str(i))
        for num, notebook in enumerate(notebooks):
            if num % 2:
                self.service.delete_notebook(notebook.id)
                with self.assertRaises(DBusException):
                    self.service.get_notebook(notebook.id)
                notebooks.remove(notebook)
        self.assertEqual(
            self._to_ids(notebooks), self._to_ids(map(
                Notebook.from_tuple, self.service.list_notebooks(),
            )),
        )
        for num, notebook in enumerate(notebooks):
            notebook.name += '*'
            if num % 2:
                self.service.delete_notebook(notebook.id)
                with self.assertRaises(DBusException):
                    self.service.update_notebook(notebook.struct)
            else:
                updated = Notebook.from_tuple(
                    self.service.update_notebook(notebook.struct),
                )
                self.assertEqual(notebook.name, updated.name)

    def test_notes_with_notebook_and_places(self):
        """Test notes with notebook and places"""
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test', None),
        )
        notes = []
        get_place = lambda num: '123' if num < 50 else '456'
        for i in range(100):
            notes.append(Note.from_tuple(self.service.create_note(Note(
                id=const.NONE_ID,
                title='New note',
                content="New note content",
                tags=['123', '345'],
                notebook=notebook.id,
                created=const.NONE_VAL,
                updated=const.NONE_VAL,
                place=get_place(i),
            ).struct)))
        filtered = []
        for num, note in enumerate(notes):
            if not num % 2:
                self.service.update_note(note.struct)  # mark note exist
                filtered.append(note)
        notes = filtered  # notes.remove(note) not work, wtf
        self.assertEqual(
            self._to_ids(notes), self._to_ids(map(
                Note.from_tuple, self.service.find_notes(
                    '', dbus.Array([], signature='i'),
                    dbus.Array([], signature='i'), 0,
                    100, const.ORDER_UPDATED_DESC, -1,
                ),
            )),
        )
        filtered = []
        for num, note in enumerate(notes):
            note.title += '*'
            if num % 2:
                self.service.delete_note(note.id)
                with self.assertRaises(DBusException):
                    self.service.update_note(note.struct)
            else:
                updated = Note.from_tuple(
                    self.service.update_note(note.struct),
                )
                self.assertEqual(note.title, updated.title)
                filtered.append(updated)
        self.assertEqual(len(filtered),
            self.service.get_notebook_notes_count(notebook.id),
        )
        self.assertEqual(set(['123', '456']), set(map(
            lambda place: Place.from_tuple(place).name,
            self.service.list_places(),
        )))

    def test_tags(self):
        """Test tags"""
        tags = map(str, range(100))
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test', None),
        )
        self.service.create_note(Note(
            id=const.NONE_ID,
            title='New note',
            content="New note content",
            tags=tags,
            notebook=notebook.id,
            created=const.NONE_VAL,
            updated=const.NONE_VAL,
            place='',
        ).struct)
        remote_tags = map(Tag.from_tuple, self.service.list_tags())
        self.assertEqual(set(tags), set(map(
            lambda tag: tag.name, remote_tags,
        )))
        filtered = []
        for num, tag in enumerate(remote_tags):
            if num % 2:
                filtered.append(tag)
            else:
                self.service.delete_tag(tag.id)
        tags = filtered  # tags.remove(tag) not work, wtf
        self.assertEqual(
            self._to_ids(tags), self._to_ids(map(
                Tag.from_tuple, self.service.list_tags(),
            )),
        )
        filtered = []
        for num, tag in enumerate(tags):
            tag.name += '*'
            if num % 2:
                self.service.delete_tag(tag.id)
                with self.assertRaises(DBusException):
                    self.service.update_tag(tag.struct)
            else:
                updated = Tag.from_tuple(
                    self.service.update_tag(tag.struct),
                )
                self.assertEqual(tag.name, updated.name)
                filtered.append(updated)

    def _file_names(self, items):
        return set(map(lambda item: item.file_name, items))

    def test_note_resources(self):
        """Test note resources"""
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test', None),
        )
        struct = self.service.create_note(Note(
            id=const.NONE_ID,
            title='New note',
            content="New note content",
            tags=[],
            notebook=notebook.id,
            created=const.NONE_VAL,
            updated=const.NONE_VAL,
            place='',
        ).struct)
        note = Note.from_tuple(self.service.update_note(struct))
        resources = []
        for i in range(100):
            resources.append(Resource(
                id=const.NONE_ID,
                file_name="name/%d" % i,
                file_path="path/%d" % i,
                mime='image/png',
                hash='',
            ))
        self.service.update_note_resources(note.struct,
            map(lambda resource: resource.struct, resources),
        )
        received = map(Resource.from_tuple,
            self.service.get_note_resources(note.id))
        self.assertEqual(
            self._file_names(resources), self._file_names(received),
        )
        received = received[:50]
        self.service.update_note_resources(note.struct,
            map(lambda resource: resource.struct, received),
        )
        new_received = map(Resource.from_tuple,
            self.service.get_note_resources(note.id))
        self.assertEqual(
            self._file_names(new_received), self._file_names(received),
        )

    def test_note_conflicts_serialisation(self):
        """Test notes with conflict serialisztion"""
        parent = models.Note(
            title='123',
            content='456',
        )
        self.session.add(parent)
        self.session.commit()
        conflicts = []
        for i in range(10):
            conflict = models.Note(
                title='123',
                content='456',
                conflict_parent_id=parent.id,
            )
            self.session.add(conflict)
            conflicts.append(conflict)
        self.session.commit()
        self.assertEqual(
            set(parent.conflict_items_dbus),
            self._to_ids(conflicts),
        )
        for conflict in conflicts:
            self.assertEqual(parent.id,
                conflict.conflict_parent_dbus)

    def test_tag_delete(self):
        """Test deleting tags"""
        tag = models.Tag(
            name='okok',
            action=models.ACTION_NONE,
        )
        deleting_tag = models.Tag(
            name='deleted',
            action=models.ACTION_NONE,
        )
        self.session.add(tag)
        self.session.add(deleting_tag)
        note = models.Note(
            title='123',
            content='456',
            tags=[tag, deleting_tag],
        )
        self.session.add(note)
        self.session.commit()
        self.service.delete_tag(deleting_tag.id)
        self.assertItemsEqual(note.tags, [tag])

    def test_notebook_count_with_conflicts(self):
        """Test notebook notes count with conflict versions"""
        notebook = models.Notebook(
            name='notebook',
        )
        self.session.add(notebook)
        original_note = models.Note(
            title='123',
            content='456',
            notebook=notebook,
            action=models.ACTION_CREATE,
        )
        self.session.add(original_note)
        self.session.commit()

        self.assertEqual(self.service.get_notebook_notes_count(
            notebook.id
        ), 1)

        conflict_note = models.Note(
            title='123',
            content='456',
            notebook=notebook,
            action=models.ACTION_CONFLICT,
            conflict_parent=[original_note],
        )
        self.session.add(conflict_note)
        self.session.commit()

        self.assertEqual(self.service.get_notebook_notes_count(
            notebook.id
        ), 1)

    def test_get_note_by_guid(self):
        """Test getting note by guid"""
        title = '123'
        guid = '456'

        note = models.Note(
            title=title,
            content='456',
            action=models.ACTION_NONE,
            guid=guid,
        )
        self.session.add(note)
        self.session.commit()

        service_note = Note.from_tuple(self.service.get_note_by_guid(guid))
        self.assertEqual(service_note.title, title)

    def test_get_note_by_guid_with_conflicts(self):
        """Test getting note by guid with conflicts"""
        title = '123'
        guid = '456'

        note = models.Note(
            title=title,
            content='456',
            action=models.ACTION_NONE,
            guid=guid,
        )
        self.session.add(note)
        self.session.commit()

        conflict_note = models.Note(
            title='asd',
            content='456',
            action=models.ACTION_CONFLICT,
            guid=guid,
            conflict_parent=[note],
        )
        self.session.add(conflict_note)
        self.session.commit()

        service_note = Note.from_tuple(self.service.get_note_by_guid(guid))
        self.assertEqual(service_note.title, title)


class FindTestCase(unittest.TestCase):
    """Find notes method test case"""

    def setUp(self):
        self._create_service()
        self._create_notebooks()
        self._create_notes()

    def _create_notes(self):
        """Create notes"""
        notes = [
            self.service.create_note(Note(
                id=const.NONE_ID,
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
                id=const.NONE_ID,
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
                id=const.NONE_ID,
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
                id=const.NONE_ID,
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
                id=const.NONE_ID,
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
        self.service.qobject = MagicMock()
        self.service.app = MagicMock()
        self.service.sync = MagicMock()

    def test_get_note(self):
        """Test get note method"""
        note = models.Note(
            title='title',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        remote_note = btype.Note << self.service.get_note(note.id)
        self.assertEqual(remote_note.title, note.title)

    def test_get_note_by_guid(self):
        """Test get note method"""
        note = models.Note(
            title='title',
            guid='guid',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        remote_note = btype.Note << self.service.get_note_by_guid(note.guid)
        self.assertEqual(remote_note.title, note.title)

    def test_get_note_alternatives(self):
        """Test get note alternatives"""
        note = models.Note(
            title='title',
            guid='guid',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        alternative = models.Note(
            title='title',
            guid='guid',
            action=const.ACTION_CONFLICT,
            conflict_parent_id=note.id,
        )
        self.session.add(alternative)
        self.session.commit()

        remote_notes = btype.Note.list << self.service.get_note_alternatives(
            note.id,
        )
        self.assertEqual(remote_notes[0].id, alternative.id)

    def test_list_notebooks(self):
        """Test list notebooks method"""
        notebooks = []
        for name in range(10):
            notebook = models.Notebook(
                name=str(name),
                action=const.ACTION_NONE,
            )
            self.session.add(notebook)
            self.session.commit()
            notebooks.append(notebook.id)

        remote_notebooks = btype.Notebook.list << self.service.list_notebooks()
        ids = [notebook.id for notebook in remote_notebooks]

        self.assertItemsEqual(notebooks, ids)

    def test_get_notebook(self):
        """Test get notebook method"""
        notebook = models.Notebook(
            name='notebook',
            action=const.ACTION_NONE,
        )
        deleted_notebook = models.Notebook(
            name='deleted notebook',
            action=const.ACTION_DELETE,
        )
        self.session.add(notebook)
        self.session.add(deleted_notebook)
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
        notebook = models.Notebook(
            name='notebook',
            action=const.ACTION_NONE,
        )
        self.session.add(notebook)

        count = 10
        for i in range(count):
            self.session.add(models.Note(
                title='note',
                action=const.ACTION_NONE,
                notebook=notebook,
            ))
        self.session.commit()

        self.assertEqual(
            self.service.get_notebook_notes_count(notebook.id), 10,
        )

    def test_update_notebook(self):
        """Test update notebook method"""
        notebook = models.Notebook(
            name='notebook',
            action=const.ACTION_NONE,
        )
        self.session.add(notebook)
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
        notebook = models.Notebook(
            name='notebook',
            action=const.ACTION_NONE,
        )
        self.session.add(notebook)
        self.session.commit()

        self.service.delete_notebook(notebook.id)

        self.assertEqual(notebook.action, const.ACTION_DELETE)

    def test_list_tags(self):
        """Test list tags"""
        tags = []

        for name in range(10):
            tag = models.Tag(
                name=str(name),
                action=const.ACTION_NONE,
            )
            self.session.add(tag)
            self.session.commit()
            tags.append(tag.id)

        remote_tags = btype.Tag.list << self.service.list_tags()
        tags_ids = [tag.id for tag in remote_tags]

        self.assertEqual(tags_ids, tags)

    def test_get_tag_notes_count(self):
        """Test get tag notes count method"""
        tag = models.Tag(
            name='tag',
            action=const.ACTION_NONE,
        )
        self.session.add(tag)

        count = 10
        for i in range(count):
            self.session.add(models.Note(
                title='note',
                action=const.ACTION_NONE,
                tags=[tag],
            ))
        self.session.commit()

        self.assertEqual(
            self.service.get_tag_notes_count(tag.id), 10,
        )

    def test_delete_tag(self):
        """Test delete tag"""
        tag = models.Tag(
            name='tag',
            action=const.ACTION_NONE,
        )
        self.session.add(tag)
        self.session.commit()

        self.service.delete_tag(tag.id)

        self.assertEqual(tag.action, const.ACTION_DELETE)

    def test_update_tag(self):
        """Test update tag method"""
        tag = models.Tag(
            name='tag',
            action=const.ACTION_NONE,
        )
        self.session.add(tag)
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
        title = 'note'
        note_btype = btype.Note(
            title=title,
            tags=[],
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
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

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
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        resource = models.Resource(
            file_name='name',
            action=const.ACTION_NONE,
            note_id=note.id,
        )
        self.session.add(resource)
        self.session.commit()

        resources_btype = btype.Resource.list << self.service.get_note_resources(
            note.id,
        )

        self.assertEqual(resources_btype[0].file_name, resource.file_name)

    def test_update_note_resources(self):
        """Test update note resources"""
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

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
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

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
        place_ids = []
        for num in range(10):
            place = models.Place(
                name='{}'.format(num),
            )
            self.session.add(place)
            self.session.commit()
            place_ids.append(place.id)

        places_btype = btype.Place.list << self.service.list_places()
        for place_btype in places_btype:
            self.assertIn(place_btype.id, place_ids)

    def test_share_note(self):
        """Test share note"""
        note = models.Note(
            title='note',
            action=const.ACTION_NONE,
        )
        self.session.add(note)
        self.session.commit()

        self.service.share_note(note.id)
        self.assertEqual(note.share_status, const.SHARE_NEED_SHARE)
        self.service.sync.assert_called_once_with()
