from PySide.QtGui import QTreeView, QItemSelection
from PySide.QtCore import Signal


class EverpadTreeView(QTreeView):
    selection = Signal(QItemSelection, QItemSelection)

    def selectionChanged(self, selected, deselected):
        QTreeView.selectionChanged(self, selected, deselected)
        self.selection.emit(selected, deselected)
