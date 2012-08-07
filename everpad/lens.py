import sys
sys.path.append('..')
from singlet.lens import SingleScopeLens, IconViewCategory, ListViewCategory
from everpad.tools import provider
from everpad.basetypes import Note, Tag, Notebook
import dbus


class EverpadLens(SingleScopeLens):
    class Meta:
        name = 'everpad'
        description = 'Everpad Lens'
        search_hint = 'Search Everpad'
        icon = '../everpad.png'
        search_on_blank=False

    category = ListViewCategory("Notes", 'help')

    def search(self, search, results):
        for note_struct in provider.find_notes(
            search, dbus.Array([], signature='i'),
            dbus.Array([], signature='i'), 100,
            Note.ORDER_TITLE,
        ):
            note = Note.from_tuple(note_struct)
            results.append(
                'everpad --open %d' % note.id,
                'everpad', self.category, "text/html",
                note.title, '', ''
            )


def main():
    pass

if __name__ == '__main__':
    main()
