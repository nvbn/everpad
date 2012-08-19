import dbus
import keyring


def get_provider(bus=None):
    if not bus: bus = dbus.SessionBus()
    provider = bus.get_object("com.everpad.Provider", '/EverpadProvider')
    dbus.Interface(provider, "com.everpad.Provider")
    return provider


def get_pad(bus=None):
    if not bus: bus = dbus.SessionBus()
    pad = bus.get_object("com.everpad.App", "/EverpadService")
    dbus.Interface(pad, "com.everpad.App")
    return pad


def get_auth_token():
    return keyring.get_password('everpad', 'oauth_token')
