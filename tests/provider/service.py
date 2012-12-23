import sys
sys.path.insert(0, '..')
import settings
from dbus.exceptions import DBusException
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import (
    Note, Notebook, Tag, Resource, NONE_ID, NONE_VAL,
)
from everpad.provider import models
import unittest
import dbus


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ProviderService()
        self.service._session = get_db_session()
        models.Note.session = self.service._session  # TODO: fix that shit

    def _to_ids(self, items):
        return set(map(lambda item: item.id, items))

    def test_notebooks(self):
        """Test notebooks"""
        notebooks = []
        for i in range(100):
            notebooks.append(Notebook.from_tuple(
                self.service.create_notebook(str(i)),
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

    def test_notes_with_notebook(self):
        """Test notes with notebook"""
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test'),
        )
        notes = []
        for i in range(100):
            notes.append(Note.from_tuple(self.service.create_note(Note(
                id=NONE_ID,
                title='New note',
                content="New note content",
                tags=dbus.Array([], signature='s'),
                notebook=notebook.id,
                created=NONE_VAL,
                updated=NONE_VAL,
                place='',
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

    def test_tags(self):
        """Test tags"""
        tags = map(str, range(100))
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test'),
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


if __name__ == '__main__':
    unittest.main()
