import dbus
import dbus.service


class UnityLauncher(dbus.service.Object):
    def __init__(self, app_uri, *args, **kwargs):
        self.app_uri = app_uri
        self.data = {}
        dbus.service.Object.__init__(self, *args, **kwargs)

    def update(self, data):
        self.data = data
        self.Update(self.app_uri, data)

    @dbus.service.signal(
        dbus_interface='com.canonical.Unity.LauncherEntry',
        signature=("sa{sv}")
    )
    def Update(self, app_uri, properties):
        return

    @dbus.service.method(
        dbus_interface='com.canonical.Unity.LauncherEntry',
        in_signature="", out_signature="sa{sv}",
    )
    def Query(self):
        return self.app_uri, self.data
