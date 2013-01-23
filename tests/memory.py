from everpad.basetypes import Note
from random import randint
from copy import deepcopy
from guppy import hpy
import unittest


class NoteGenerator(object):

    def __init__(self, count):
        self._count = count
        self._pool = []
        self._title = u'Note title'
        with open('test_content.txt') as content:
            self._content = unicode(content.read())
        self._tags = map(lambda num: u"tag_%d" % num, range(30))
        self._place = u'Test place from test city'
        self._url = 'http://evernote/share_note/guid/etc'

    def generate(self):
        for counter in range(self._count):
            self._pool.append(self.get_note())

    def get_note(self):
        return Note(
            id=randint(1, 100000),
            title=deepcopy(self._title),
            content=deepcopy(self._content),
            created=randint(1000000, 9000000),
            updated=randint(1000000, 9000000),
            notebook=randint(1, 100000),
            tags=deepcopy(self._tags),
            place=deepcopy(self._place),
            pinnded=True,
            conflict_parent=randint(1, 100000),
            conflict_items=range(10),
            share_date=randint(1000000, 9000000),
            share_url=deepcopy(self._url),
        )


class TestMemoryConsumption(unittest.TestCase):
    def _perform_basetyp(self, count):
        heap = hpy()
        gen = NoteGenerator(count)
        gen.generate()
        print
        print 'Basetype note: %d instances' % count
        print heap.heap()
        print
        print
        print

    test_0 = lambda self: self._perform_basetyp(100)
    test_1 = lambda self: self._perform_basetyp(500)
    test_2 = lambda self: self._perform_basetyp(1000)
    test_3 = lambda self: self._perform_basetyp(5000)
    test_4 = lambda self: self._perform_basetyp(10000)


if __name__ == '__main__':
    unittest.main()
