from PySide.QtGui import QCompleter, QStringListModel, QApplication
from PySide.QtCore import Slot
from everpad.basetypes import Tag, Notebook
import re


class TagEdit(object):
    """Abstraction for tag edit"""

    def __init__(self, parent, widget, on_change):
        """Init and connect signals"""
        self.parent = parent
        self.app = QApplication.instance()
        self.widget = widget
        self.tags_list = map(lambda tag:
            Tag.from_tuple(tag).name,
            self.app.provider.list_tags(),
        )
        self.completer = QCompleter()
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.completer.activated.connect(self.update_completion)
        self.update_completion()
        self.widget.setCompleter(self.completer)
        self.widget.textChanged.connect(Slot()(on_change))
        self.widget.textEdited.connect(self.update_completion)

    @property
    def tags(self):
        """Get tags"""
        # Split on comma and Arabic comma
        # 0x060c is the Arabic comma
        return map(lambda tag: tag.strip(),
            re.split(u',|\u060c', self.widget.text()))

    @tags.setter
    def tags(self, val):
        """Set tags"""
        self.widget.setText(', '.join(val))

    @Slot()
    def update_completion(self):
        """Update completion model with exist tags"""
        orig_text = self.widget.text()
        text = ', '.join(orig_text.replace(', ', ',').split(',')[:-1])
        tags = []
        for tag in self.tags_list:
            if ',' in orig_text:
                if orig_text[-1] not in (',', ' '):
                    tags.append('%s,%s' % (text, tag))
                tags.append('%s, %s' % (text, tag))
            else:
                tags.append(tag)
        if tags != self.completer_model.stringList():
            self.completer_model.setStringList(tags)


class NotebookEdit(object):
    """Abstraction for notebook edit"""

    def __init__(self, parent, widget, on_change):
        """Init and connect signals"""
        self.parent = parent
        self.app = QApplication.instance()
        self.widget = widget
        for notebook_struct in self.app.provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            self.widget.addItem(notebook.name, userData=notebook.id)
        self.widget.currentIndexChanged.connect(Slot()(on_change))

    @property
    def notebook(self):
        """Get notebook"""
        notebook_index = self.widget.currentIndex()
        return self.widget.itemData(notebook_index)

    @notebook.setter
    def notebook(self, val):
        """Set notebook"""
        notebook_index = self.widget.findData(val)
        self.widget.setCurrentIndex(notebook_index)
