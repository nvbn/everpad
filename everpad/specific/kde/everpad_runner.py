from PyKDE4 import plasmascript
from PyKDE4.plasma import Plasma
from PyKDE4.kdeui import KIcon, KMessageBox
from html2text import html2text
from everpad.basetypes import Note
from everpad.tools import get_provider, get_pad
import dbus


CREATE = -1
SETTINGS = -2
provider = get_provider()

 
class EverpadRunner(plasmascript.Runner):
 
    def match(self, context):
        if not context.isValid():
            return
        query = context.query()
        search = query.__str__()  # PyQt is shit
        if len(search) < 3:
            return
        if search.lower() in 'create note':
            action = Plasma.QueryMatch(self.runner)
            action.setText("Create new note in everpad")
            action.setType(Plasma.QueryMatch.ExactMatch)
            action.setIcon(KIcon("everpad"))
            action.setData(str(CREATE))
            context.addMatch(query, action)
        if search.lower() in 'settings and management':
            action = Plasma.QueryMatch(self.runner)
            action.setText("Open everpad settings")
            action.setType(Plasma.QueryMatch.ExactMatch)
            action.setIcon(KIcon("everpad"))
            action.setData(str(SETTINGS))
            context.addMatch(query, action)
        blank = dbus.Array([], signature='i')
        for note_struct in provider.find_notes(
            search, blank, blank, 0,
            1000, Note.ORDER_TITLE, -1,
        ):
            note = Note.from_tuple(note_struct)
            action = Plasma.QueryMatch(self.runner)
            action.setText(note.title)
            content = html2text(note.content)
            content = content[:200]
            action.setSubtext(content)
            action.setType(Plasma.QueryMatch.ExactMatch)
            action.setIcon(KIcon("everpad"))
            action.setData(str(note.id))
            context.addMatch(query, action)

 
    def run(self, context, match):
        data = match.data().toInt()[0]
        pad = get_pad()
        if data == CREATE:
            pad.create()
        elif data == SETTINGS:
            pad.settings()
        else:
            pad.open(data)
 
 
def CreateRunner(parent):
    return EverpadRunner(parent)
