import sys
sys.path.insert(0, '..')
import settings
from dbus.exceptions import DBusException
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import Note, Notebook, Tag, Resource
import unittest


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ProviderService()
        self.service._session = get_db_session()

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
        for notebook in notebooks:
            self.service.delete_notebook(notebook.id)
            with self.assertRaises(DBusException):
                self.service.get_notebook(notebook.id)
            notebooks.remove(notebook)
        self.assertEqual(
            self._to_ids(notebooks), self._to_ids(map(
                Notebook.from_tuple, self.service.list_notebooks(),
            )),
        )


if __name__ == '__main__':
    unittest.main()
