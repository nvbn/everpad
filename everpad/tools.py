from functools import wraps, partial
from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser
from everpad.const import API_VERSION, SCHEMA_VERSION, VERSION
import dbus
import re
import sys
import os
import pkg_resources


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
    if not bus:
        bus = dbus.SessionBus()
    provider = bus.get_object("com.everpad.Provider", '/EverpadProvider')
    return dbus.Interface(provider, "com.everpad.Provider")


@wrapper_functor
def get_pad(bus=None):
    if not bus:
        bus = dbus.SessionBus()
    pad = bus.get_object("com.everpad.App", "/EverpadService")
    return dbus.Interface(pad, "com.everpad.App")


def clean(text):  # from http://stackoverflow.com/questions/1707890/fast-way-to-filter-illegal-xml-unicode-chars-in-python
    illegal_unichrs = [
        (0x00, 0x08), (0x0B, 0x1F), (0x7F, 0x84), (0x86, 0x9F),
        (0xD800, 0xDFFF), (0xFDD0, 0xFDDF), (0xFFFE, 0xFFFF),
        (0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF), (0x3FFFE, 0x3FFFF),
        (0x4FFFE, 0x4FFFF), (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
        (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF), (0x9FFFE, 0x9FFFF),
        (0xAFFFE, 0xAFFFF), (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
        (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF), (0xFFFFE, 0xFFFFF),
        (0x10FFFE, 0x10FFFF)
    ]

    illegal_ranges = [
        "%s-%s" % (unichr(low), unichr(high))
        for (low, high) in illegal_unichrs
        if low < sys.maxunicode
    ]
    illegal_xml_re = re.compile(u'[%s]' % u''.join(illegal_ranges))
    return illegal_xml_re.sub('', text)


def sanitize(soup=None, html=None):
    _allowed_tags = (
        'a', 'abbr', 'acronym', 'address', 'area', 'b', 'bdo',
        'big', 'blockquote', 'br', 'caption', 'center', 'cite',
        'code', 'col', 'colgroup', 'dd', 'del', 'dfn', 'div',
        'dl', 'dt', 'em', 'font', 'h1', 'h2', 'h3', 'h4', 'h5',
        'h6', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'map', 'ol',
        'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
        'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot',
        'th', 'thead', 'title', 'tr', 'tt', 'u', 'ul', 'var', 'xmp',
        'en-media', 'en-todo', 'en-crypt',
    )
    _disallowed_attrs = (
        'id', 'class', 'onclick', 'ondblclick', 'rel',
        'accesskey', 'data', 'dynsrc', 'tabindex', 'typeof',
        'property',
    )
    _protocols = (
        'http', 'https', 'file', 'evernote',
    )
    if not soup:
        soup = BeautifulSoup(html)
    for tag in soup.findAll(True):
        if tag.name in _allowed_tags:
            for attr in _disallowed_attrs:
                try:
                    del tag[attr]
                except KeyError:
                    pass
            try:
                if not sum(map(
                    lambda proto: tag['href'].find(proto + '://') == 0,
                _protocols)):
                    del tag['href']
            except KeyError:
                pass
        else:
            tag.hidden = True
    return clean(reduce(
         lambda txt, cur: txt + unicode(cur), soup.contents,
    u''))


def html_unescape(html):
    return HTMLParser().unescape(html)


def print_version():
    print 'Everpad version: %s' % VERSION
    print 'API version: %d' % API_VERSION
    print 'Schema version: %d' % SCHEMA_VERSION
    sys.exit(0)


def get_proxy_config(scheme):
    for fmt in ('%s_proxy', '%s_PROXY'):
        proxy = os.environ.get(fmt % scheme)
        if proxy is not None:
            return proxy
    return None


def prepare_file_path(dest, file_name):
    file_path = os.path.join(dest, file_name)
    iteration = 0
    while os.path.isfile(file_path):
        file_path = os.path.join(dest, '%d_%s' % (
            iteration, file_name,
        ))
        iteration += 1
    return file_path


def resource_filename(file_name):
    paths = map(
        lambda path: os.path.join(path, file_name),
        (
            '/opt/extras.ubuntu.com/',
            '/usr/local/',
            '/usr/',
        ),
    )
    for path in paths:
        if os.path.isfile(path):
            return path
    return pkg_resources.resource_filename(
        pkg_resources.Requirement.parse("everpad"), file_name)
