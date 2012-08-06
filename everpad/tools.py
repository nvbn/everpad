import dbus


def get_provider():
    provider_obj = dbus.SessionBus().get_object("com.everpad.Provider", '/EverpadProvider')
    dbus.Interface(provider_obj, "com.everpad.Provider")
    return provider_obj
provider = get_provider()
