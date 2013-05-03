from everpad.basetypes import Tag, DbusSendable
import unittest


class TestBaseTypes(unittest.TestCase):
    def test_signature(self):
        class Fake(DbusSendable):
            fields = (
                ('id', 'i'),
                ('name', 's'),
            )
        self.assertEqual(
            Fake.signature, '(is)',
            'generate signature',
        )

    def test_serialise(self):
        class Fake(object):
            id = 0
            name = '123'
        tag = Tag.from_obj(Fake())
        self.assertEqual(
            tag.struct, (0, '123'),
            'serialise to struct',
        )

    def test_load(self):
        tag = Tag.from_tuple((0, '123'))
        self.assertEqual(
            tag.name, '123',
            'load from struct',
        )

    def test_give(self):
        class Fake(object):
            id = 0
            @property
            def id_dbus(self):
                return self.id

            @id_dbus.setter
            def id_dbus(self, val):
                self.id = val + 12
        tag = Tag.from_tuple((0, '123'))
        obj = Fake()
        tag.give_to_obj(obj)
        self.assertEqual(
            obj.id, 12,
            'give data to object',
        )
