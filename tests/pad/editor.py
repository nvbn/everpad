import sys
sys.path.insert(0, '..')
import settings
from PySide.QtGui import QApplication
from PySide.QtCore import QSettings
from dbus.exceptions import DBusException
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import (
    Note, Notebook, Tag, Resource, Place,
    NONE_ID, NONE_VAL,
)
from everpad.provider import models
from everpad.pad.editor import Editor
from datetime import datetime
import dbus
import unittest


class FakeApp(QApplication):
    def update(self, service):
        self.provider = service
        self.settings = QSettings('everpad-test', str(datetime.now()))


app = FakeApp(sys.argv)

CONTENTS = [
    u"<ul><li>23</li><li>567</li></ul>",
    u"<p>123</p>\xa0\xa0ok",
    u"<p>\xa0\xa0123</p><p>\xa0\xa0\xa0\xa0ok</p>",
    u"<p>hello, i'am fat</p>",
    u"<ul><li>1</li><li><ul><li>2</li><li>3</li></ul></li><li>4</li></ul>",
]


class EditorTestCase(unittest.TestCase):
    def setUp(self):
        self.service = ProviderService()
        self.service._session = get_db_session()
        models.Note.session = self.service._session 
        self.app = app
        app.update(self.service)
        notebook = Notebook.from_tuple(
            self.service.create_notebook('test'),
        )
        self.note = Note.from_tuple(self.service.create_note(Note(
            id=NONE_ID,
            title='New note',
            content="New note content",
            tags=[],
            notebook=notebook.id,
            created=NONE_VAL,
            updated=NONE_VAL,
            place='',
        ).struct))

    def test_content_nochange(self):
        """Test content nochange"""
        editor = Editor(self.note)
        self.assertEqual(
            editor.note_edit.content,
            "New note content",
        )
        for content in CONTENTS:
            editor.note_edit.content = content
            self.assertEqual(
                editor.note_edit.content,
                content,
            )


if __name__ == '__main__':
    unittest.main()
