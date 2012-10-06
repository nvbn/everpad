from functools import wraps, partial
import dbus


class InterfaceWrapper(object):
    def __init__(self, get):
        self.__get = get
        self.__load()

    def __load(self):
        self.__interface = self.__get()

    def __getattr__(self, name):
        attr = getattr(self.__interface, name)
        if hasattr(attr, '__call__'):
            attr = self.__reconnect_on_fail(attr, name)
        return attr

    def __reconnect_on_fail(self, fnc, name):
        def wrapper(*args, **kwargs):
            try:
                return fnc(*args, **kwargs)
            except dbus.DBusException:
                self.__load()
                return getattr(self.__interface, name)(*args, **kwargs)
        return wrapper

def wrapper_functor(fnc):
    @wraps(fnc)
    def wrapper(*args, **kwrags):
        return InterfaceWrapper(partial(fnc, *args, **kwrags))
    return wrapper


@wrapper_functor
def get_provider(bus=None):
    if not bus: bus = dbus.SessionBus()
    provider = bus.get_object("com.everpad.Provider", '/EverpadProvider')
    return dbus.Interface(provider, "com.everpad.Provider")


@wrapper_functor
def get_pad(bus=None):
    if not bus: bus = dbus.SessionBus()
    pad = bus.get_object("com.everpad.App", "/EverpadService")
    return dbus.Interface(pad, "com.everpad.App")


def get_auth_token():
    import keyring
    return keyring.get_password('everpad', 'oauth_token')
