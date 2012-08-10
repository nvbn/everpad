import sys
sys.path.append('..')
from singlet.lens import SingleScopeLens, IconViewCategory, ListViewCategory
from gi.repository import Gio, Unity
from singlet.utils import run_lens
from everpad.tools import get_provider
from everpad.basetypes import Note, Tag, Notebook
import dbus
import sys
provider = get_provider()


class EverpadLens(SingleScopeLens):

    class Meta:
        name = 'everpad'
        description = 'Everpad Lens'
        search_hint = 'Search Everpad'
        icon = '../everpad.png'
        search_on_blank = True
        bus_name = 'net.launchpad.Unity.Lens.EverpadLens'
        bus_path = '/net/launchpad/unity/lens/everpad'

    def __init__(self):
        SingleScopeLens.__init__(self)
        icon = Gio.ThemedIcon.new("/usr/share/icons/unity-icon-theme/places/svg/group-recent.svg")
        tags = Unity.CheckOptionFilter.new('tags', 'Tags', icon, True)
        for tag_struct in provider.list_tags():
            tag = Tag.from_tuple(tag_struct)
            tags.add_option(str(tag.id), tag.name, icon)
        notebooks = Unity.RadioOptionFilter.new('notebooks', 'Notebooks', icon, True)
        for notebook_struct in provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            notebooks.add_option(str(notebook.id), notebook.name, icon)
        self._lens.props.filters = [notebooks, tags]

    category = IconViewCategory("Notes", 'everpad')

    def search(self, search, results):
        if self.notebook_filter_id:
            notebooks = [self.notebook_filter_id]
        else:
            notebooks = dbus.Array([], signature='i')
        tags = dbus.Array(self.tag_filter_ids, signature='i')
        for note_struct in provider.find_notes(
            search, notebooks, tags, 100, Note.ORDER_TITLE,
        ):
            note = Note.from_tuple(note_struct)
            results.append(
                'everpad --open %d' % note.id,
                'everpad', self.category, "text/html",
                note.title, '', ''
            )

    def on_filtering_changed(self, scope):
        tags = scope.get_filter('tags')
        self.tag_filter_ids = map(lambda tag: int(tag.props.id), 
            filter(lambda tag: tag.props.active, tags.options))
        notebook = scope.get_filter('notebooks').get_active_option()
        if notebook:
            self.notebook_filter_id = int(notebook.props.id)
        else:
            self.notebook_filter_id = None
        SingleScopeLens.on_filtering_changed(self, scope)


def main():
    run_lens(EverpadLens, sys.argv)

if __name__ == '__main__':
    main()
