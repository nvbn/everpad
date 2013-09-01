from .. import settings
from mock import MagicMock
from PySide.QtCore import QSettings, Signal, QUrl
from PySide.QtGui import QApplication
from everpad.provider.service import ProviderService
from everpad.provider.tools import get_db_session
from everpad.basetypes import (
    Note, Notebook, Tag, Resource, Place,
    NONE_ID, NONE_VAL,
)
from everpad.provider import models
from everpad.pad.editor import Editor
from everpad.pad.editor.content import set_links
from datetime import datetime
import unittest
import sys
import os


class FakeApp(QApplication):
    data_changed = Signal()

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

CHANGING_CONTENTS = [
    (u"<p>< a b cd</p>", u"<p>&lt; a b cd</p>"),
    (u"> a b cd", u"&gt; a b cd"),
    (u"<p>ok</p><a b cd", u"<p>ok</p>"),
]

TITLES = [
    u"&lt;&lt;ok ok ok",
    ''.join([u"verybigtitle"] * 50),
    u"ok<p asdasd",
]

SET_LINKS = [
    (u"without", u"without"),
    (u"https://github.com/nvbn/", u'<a href="https://github.com/nvbn/">https://github.com/nvbn/</a>'),
    (u"https://github.com/nvbn/ http://ya.ru/", u'<a href="https://github.com/nvbn/">https://github.com/nvbn/</a> <a href="http://ya.ru/">http://ya.ru/</a>'),
    (u"<p>https://github.com/nvbn/</p>", u"<p>https://github.com/nvbn/</p>"),
]


if 'test_editor' in os.environ:
    class EditorTestCase(unittest.TestCase):
        def setUp(self):
            self.service = ProviderService()
            self.service._session = get_db_session()
            models.Note.session = self.service._session
            self.app = app
            self.app.update(self.service)
            notebook = Notebook.from_tuple(
                self.service.create_notebook('test', None),
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

        def tearDown(self):
            if hasattr(self, 'editor'):
                self.app.data_changed.disconnect(
                    self.editor.init_alternatives,
                )
            del self.app.provider
            del self.app

        def test_content_nochange(self):
            """Test content nochange"""
            self.editor = Editor(self.note)
            self.assertEqual(
                self.editor.note_edit.content,
                "New note content",
            )
            for content in CONTENTS:
                self.editor.note_edit.content = content
                self.assertEqual(
                    self.editor.note_edit.content,
                    content,
                )

        def test_content_changing(self):
            """Test content changing"""
            self.editor = Editor(self.note)
            for prev, current in CHANGING_CONTENTS:
                self.editor.note_edit.content = prev
                self.assertEqual(
                    self.editor.note_edit.content,
                    current,
                )

        def test_title_nochange(self):
            """Test title nochange"""
            self.editor = Editor(self.note)
            self.assertEqual(
                self.editor.note_edit.title,
                "New note",
            )
            for title in TITLES:
                self.editor.note_edit.title = title
                self.assertEqual(
                    self.editor.note_edit.title,
                    title,
                )

        def test_set_links(self):
            """Test set links"""
            for orig, result in SET_LINKS:
                self.assertEqual(
                    set_links(orig), result,
                )

        def test_not_broken_note_links(self):
            """Test content nochange"""
            content = '<a href="evernote:///view/123/123/123/">note link</a>'
            self.note.content = content
            self.editor = Editor(self.note)
            self.assertEqual(
                self.editor.note_edit.content,
                content,
            )

        def test_open_note_links(self):
            """Test open note links"""
            guid = 'guid'
            note = Note(
                id=123,
            )

            self.app.open = MagicMock()
            self.service.get_note_by_guid = MagicMock(
                return_value=note.struct,
            )

            link = "evernote:///view/123/123/{guid}/123/".format(
                guid=guid,
            )
            self.editor = Editor(self.note)
            self.editor.note_edit.link_clicked(QUrl(link))

            self.assertEqual(
                self.service.get_note_by_guid.call_args[0][0], guid,
            )
            self.assertEqual(
                self.app.open.call_args[0][0].id, note.id,
            )
            del self.app.open
