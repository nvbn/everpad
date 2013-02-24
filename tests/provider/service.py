# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '..')
# patch settings:
import settings

from dbus.exceptions import DBusException
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import (
    Note, Notebook, Tag, Resource, Place,
    NONE_ID, NONE_VAL,
)
from everpad.provider import models
import unittest
import dbus


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
                id=NONE_ID,
                title='New note',
                content="New note content",
                tags=['123', '345'],
                notebook=notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
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
                    100, Note.ORDER_UPDATED_DESC, -1,
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
            id=NONE_ID,
            title='New note',
            content="New note content",
            tags=tags,
            notebook=notebook.id,
            created=NONE_VAL,
            updated=NONE_VAL,
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
            id=NONE_ID,
            title='New note',
            content="New note content",
            tags=[],
            notebook=notebook.id,
            created=NONE_VAL,
            updated=NONE_VAL,
            place='',
        ).struct)
        note = Note.from_tuple(self.service.update_note(struct))
        resources = []
        for i in range(100):
            resources.append(Resource(
                id=NONE_ID,
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


class FindTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ProviderService()
        self.service._session = get_db_session()
        models.Note.session = self.service._session  # TODO: fix that shit
        self.notebook = Notebook.from_tuple(
            self.service.create_notebook('test', None),
        )
        self.notebook2 = Notebook.from_tuple(
            self.service.create_notebook('test2', None),
        )
        self.notebook3 = Notebook.from_tuple(
            self.service.create_notebook(u'Блокнот', None),
        )
        notes = [
            self.service.create_note(Note(
                id=NONE_ID,
                title='New note',
                content="New note content",
                tags=['ab', 'cd'],
                notebook=self.notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place='first',
                pinnded=False,
            ).struct),
            self.service.create_note(Note(
                id=NONE_ID,
                title='Old note',
                content="Old note content",
                tags=['ef', 'gh'],
                notebook=self.notebook2.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place='second',
                pinnded=False,
            ).struct),
            self.service.create_note(Note(
                id=NONE_ID,
                title='not',
                content="oke",
                tags=['ab', 'gh'],
                notebook=self.notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place='second',
                pinnded=True,
            ).struct),
            self.service.create_note(Note(
                id=NONE_ID,
                title=u'Заметка',
                content=u"Заметка",
                tags=[u'тэг'],
                notebook=self.notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place=u'место',
                pinnded=False,
            ).struct),
            self.service.create_note(Note(
                id=NONE_ID,
                title=u'заметка',
                content=u"заметка",
                tags=[u'тэг'],
                notebook=self.notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place=u'место',
                pinnded=False,
            ).struct),
        ]
        self.notes = map(lambda note:
            Note.from_tuple(self.service.update_note(note)),
        notes)

    def _to_ids(self, items):
        return set(map(lambda item: item.id, items))

    def _find(self, *args, **kwargs):
        return map(Note.from_tuple,
            self.service.find_notes(*args, **kwargs))

    def test_by_words(self):
        """Test notes find by words"""
        all = self._find(
            'not', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            set(self._to_ids(all)),
            set(self._to_ids(self.notes[:-2])),
        )
        two = self._find(
            'note', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            set(self._to_ids(two)),
            set(self._to_ids(self.notes[:2])),
        )
        blank = self._find(
            'not note', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(len(blank), 0)

    def test_by_tags(self):
        """Test notef find by tags"""
        tags = map(Tag.from_tuple, self.service.list_tags())
        first_last = self._find(
            '', dbus.Array([], signature='i'),
            [tags[0].id], 0, 100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            set(self._to_ids(first_last)),
            set(self._to_ids([self.notes[0], self.notes[2]])),
        )
        second = self._find(
            '', dbus.Array([], signature='i'),
            [tags[2].id], 0, 100,
            Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            self._to_ids(second), set([self.notes[1].id]),
        )
        all = self._find(
            '', dbus.Array([], signature='i'),
            map(lambda tag: tag.id, tags), 0, 100,
            Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            self._to_ids(all), self._to_ids(self.notes),
        )

    def test_by_notebooks(self):
        """Test find note by notebooks"""
        all = self._find(
            '', self._to_ids([self.notebook, self.notebook2]),
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            self._to_ids(all), self._to_ids(self.notes),
        )
        second = self._find(
            '', [self.notebook2.id],
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            self._to_ids(second), set([self.notes[1].id]),
        )

    def test_combine(self):
        """Test find by combination"""
        places = map(Place.from_tuple, self.service.list_places())
        tags = map(Tag.from_tuple, self.service.list_tags())
        first = self._find(
            'new', [self.notebook.id], [tags[0].id], places[0].id,
            100, Note.ORDER_UPDATED_DESC, False,
        )
        self.assertEqual(
            self._to_ids(first), set([self.notes[0].id]),
        )
        last = self._find(
            'oke', [self.notebook.id], [tags[0].id], places[1].id,
            100, Note.ORDER_UPDATED_DESC, True,
        )
        self.assertEqual(
            self._to_ids(last), set([self.notes[2].id]),
        )

    def test_unicode_ignorecase(self):
        """Test unicode ignorecase"""
        all = self._find(
            u'заметка', dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 0,
            100, Note.ORDER_UPDATED_DESC, -1,
        )
        self.assertEqual(
            set(self._to_ids(all)),
            set(self._to_ids(self.notes[-2:])),
        )


if __name__ == '__main__':
    unittest.main()
