#!/usr/bin/python
import dbus
import os
import sys
from gi.repository import GLib, GObject, Gio
from gi.repository import Dee
from gi.repository import Unity
import gconf
sys.path.append('..')


BUS_NAME = "net.launchpad.Unity.Lens.Everpad"


class Daemon(object):
    def __init__(self, session_bus_connection):
        self.session_bus_connection = session_bus_connection
        self._lens = Unity.Lens.new("/net/launchpad/unity/lens/everpad", "everpad")
        self._lens.props.search_hint = "Search Everpad notes"
        self._lens.props.visible = True
        self._lens.props.search_in_global = True
        self._lens.props.categories = [Unity.Category.new("All",
            Gio.ThemedIcon.new("/usr/share/icons/unity-icon-theme/places/svg/group-recent.svg"),
            Unity.CategoryRenderer.VERTICAL_TILE,
        )]
        self._scope = UserScope(self)
        self._lens.add_local_scope(self._scope.get_scope())
        self._lens.export()


class UserScope(object):
    def __init__(self, daemon):
        self._scope = Unity.Scope.new("/net/launchpad/unity/scope/everpad")
        self.settings = gconf.client_get_default()
        self._scope.connect("notify::active-search", self._on_search_changed)
        self._scope.connect("notify::active-global-search", self._on_global_search_changed)
        self._scope.connect("activate_uri", self._on_uri_activated)
        self._scope.connect("filters-changed", self._on_search_changed)
        self._scope.export()
        self.provider = Gio.DBusProxy.new_sync(daemon.session_bus_connection, 0, None, 'com.everpad.Provider',
                '/EverpadProvider', 'com.everpad.Provider', None)


    def get_scope(self):
        return self._scope

    def get_search_string(self):
        search = self._scope.props.active_search
        return search.props.search_string if search else None

    def get_global_search_string(self):
        search = self._scope.props.active_global_search
        return search.props.search_string if search else None

    def search_finished(self):
        search = self._scope.props.active_search
        if search:
            search.emit("finished")

    def global_search_finished(self):
        search = self._scope.props.active_global_search
        if search:
            search.emit("finished")

    def _on_search_changed(self, scope, param_spec=None):
        search = self.get_search_string()
        results = scope.props.results_model
        self._update_results_model(search, results)
        self.search_finished()

    def _on_global_search_changed(self, scope, param_spec):
        search = self.get_global_search_string()
        results = scope.props.global_results_model
        self._update_results_model(search, results, True)
        self.global_search_finished()

    def _update_results_model(self, search, model, is_global=False):
        model.clear()
        for entry in self.get_notes(search, is_global):
            model.append("everpad --open %s &" % entry[1],
                "everpad", 0, "application-x-desktop",
                entry[2], "All",
            "")

    def get_notes(self, search, is_global):
        return self.provider.get_notes('(si)', search or '', 1000)

    def _on_uri_activated(self, scope, uri):
        os.system(uri)
        return Unity.ActivationResponse(handled=Unity.HandledType.HIDE_DASH, goto_uri=uri)

def main():
    session_bus_connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    session_bus = Gio.DBusProxy.new_sync(session_bus_connection, 0, None,
        'org.freedesktop.DBus',
        '/org/freedesktop/DBus',
        'org.freedesktop.DBus', None)
    result = session_bus.call_sync('RequestName',
        GLib.Variant("(su)", (BUS_NAME, 0x4)),
        0, -1, None)
    result = result.unpack()[0]
    if result != 1:
        print >> sys.stderr, "Failed to own name %s. Bailing out." % BUS_NAME
        raise SystemExit(1)
    daemon = Daemon(session_bus_connection)
    GObject.MainLoop().run()

if __name__ == "__main__":
    main()