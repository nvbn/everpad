import sys
sys.path.insert(0, '..')
from singlet.lens import SingleScopeLens, ListViewCategory
from gi.repository import Gio, Unity, Notify
from singlet.utils import run_lens
from everpad.tools import get_provider, get_pad, resource_filename
from everpad.basetypes import Note, Tag, Notebook, Place, Resource
from everpad.const import API_VERSION
from html2text import html2text
from datetime import datetime
import dbus
import dbus.mainloop.glib
import sys
import os
import gettext
import json


path = os.path.join(os.path.dirname(__file__), '../../../i18n')
if not os.path.isdir(path):
    path =  resource_filename('share/locale/')
gettext.bindtextdomain('everpad', path)
gettext.textdomain('everpad')
_ = gettext.gettext

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
provider = get_provider()


class EverpadLens(SingleScopeLens):

    class Meta:
        name = 'everpad'
        description = _('Everpad Lens')
        search_hint = _('Search Everpad')
        icon = 'everpad-lens'
        search_on_blank = True
        bus_name = 'net.launchpad.Unity.Lens.EverpadLens'
        bus_path = '/net/launchpad/unity/lens/everpad'

    def __init__(self):
        SingleScopeLens.__init__(self)
        provider.connect_to_signal(
            'data_changed',
            self.update_props,
            dbus_interface="com.everpad.provider",
        )
        provider.connect_to_signal(
            'settings_changed',
            self.settings_changed,
            dbus_interface="com.everpad.provider",
        )
        self.update_props()
        self._scope.connect('preview-uri', self.preview)

    def settings_changed(self, name, value):
        if name == 'search-on-home':
            self.update_props()

    def update_props(self):
        icon = Gio.ThemedIcon.new(resource_filename(
            "share/icons/unity-icon-theme/places/svg/group-recent.svg",
        ))
        tags = Unity.CheckOptionFilter.new('tags', _('Tags'), icon, True)
        for tag_struct in provider.list_tags():
            tag = Tag.from_tuple(tag_struct)
            tags.add_option(str(tag.id), tag.name, icon)
        notebooks = Unity.RadioOptionFilter.new(
            'notebooks', _('Notebooks'), icon, True,
        )
        for notebook_struct in provider.list_notebooks():
            notebook = Notebook.from_tuple(notebook_struct)
            notebooks.add_option(str(notebook.id), notebook.name, icon)
        places = Unity.RadioOptionFilter.new('places', _('Places'), icon, True)
        for place_struct in provider.list_places():
            place = Place.from_tuple(place_struct)
            places.add_option(str(place.id), place.name, icon)
        self._lens.props.filters = [notebooks, tags, places]
        self._lens.props.search_in_global = True

    def can_search_on_home_lens(self):
        return bool(int(provider.get_settings_value('search-on-home') or 1))

    pin_notes = ListViewCategory(_("Pin Notes"), 'everpad-lens')
    all_notes = ListViewCategory(_("All Notes"), 'everpad-lens')

    def search(self, search, results):
        try:
            version = provider.get_api_version()
        except (  # dbus raise some magic
            dbus.exceptions.UnknownMethodException,
            dbus.exceptions.DBusException,
        ):
            version = -1
        if version < API_VERSION:
            dim = datetime.now() - getattr(self, 'last_api_notify', datetime.now())
            if dim.seconds > 600:
                Notify.init("everpad")
                Notify.Notification.new(
                    'everpad',
                     _('Please restart everpad via indicator'),
                '').show()
                self.last_api_notify = datetime.now()
            return
        elif version > API_VERSION:
            sys.exit(0)
        if self.notebook_filter_id:
            notebooks = [self.notebook_filter_id]
        else:
            notebooks = dbus.Array([], signature='i')
        if self.place_filter_id:
            place = self.place_filter_id
        else:
            place = 0
        tags = dbus.Array(self.tag_filter_ids, signature='i')
        for note_struct in provider.find_notes(
            search, notebooks, tags, place,
            1000, Note.ORDER_TITLE, -1,
        ):
            note = Note.from_tuple(note_struct)
            results.append(json.dumps({'id': note.id, 'search': search}),
                'everpad-note', self.pin_notes if note.pinnded else self.all_notes,
                "text/html", note.title, html2text(note.content),
            '')

    def global_search(self, phrase, results):
        if self.can_search_on_home_lens():
            return super(EverpadLens, self).global_search(phrase, results)
        else:
            results.clear()


    def preview(self, scope, uri):
        obj = json.loads(uri)
        note = Note.from_tuple(provider.get_note(obj['id']))
        preview = Unity.GenericPreview.new(
            note.title, html2text(note.content), None,
        )
        edit = Unity.PreviewAction.new("edit", "Edit", None)
        image = None
        for _res in provider.get_note_resources(note.id):
            res = Resource.from_tuple(_res)
            if 'image' in res.mime:
                image = 'file://%s' % res.file_path
        if image:
            preview.props.image_source_uri = image
        edit.connect('activated', self.handle_uri)
        preview.add_action(edit)
        return preview

    def handle_uri(self, scope, uri):
        obj = json.loads(uri)
        get_pad().open_with_search_term(int(obj['id']), obj.get('search', ''))
        return self.hide_dash_response()

    def on_filtering_changed(self, scope):
        tags = scope.get_filter('tags')
        self.tag_filter_ids = map(lambda tag: int(tag.props.id),
            filter(lambda tag: tag.props.active, tags.options))
        notebook = scope.get_filter('notebooks').get_active_option()
        if notebook:
            self.notebook_filter_id = int(notebook.props.id)
        else:
            self.notebook_filter_id = None
        place = scope.get_filter('places').get_active_option()
        if place:
            self.place_filter_id = int(place.props.id)
        else:
            self.place_filter_id = None
        SingleScopeLens.on_filtering_changed(self, scope)


def main():
    run_lens(EverpadLens, sys.argv)

if __name__ == '__main__':
    main()
