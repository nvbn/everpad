NONE_ID = 0
NONE_VAL = 0


class BaseDbusSendable(type):
    @property
    def signature(self):
        return '(' + ''.join(map(
            lambda field: field[1],
            self.fields,
        )) + ')'


class DbusSendable(object):
    __metaclass__ = BaseDbusSendable
    fields = tuple()

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)

    @classmethod
    def from_obj(cls, data):
        inst = cls()
        for field in cls.fields:
            if hasattr(data, field[0] + '_dbus'):
                val = getattr(data, field[0] + '_dbus')
            else:
                val = getattr(data, field[0], None)
            if hasattr(val, '__call__'):
                val = val()
            setattr(inst, field[0], val)
        return inst

    @classmethod
    def from_tuple(cls, data):
        inst = cls()
        for num, field in enumerate(cls.fields):
            setattr(inst, field[0], data[num])
        return inst

    @property
    def struct(self):
        result = []
        for field in self.fields:
            result.append(getattr(self, field[0], None))
        return tuple(result)

    def give_to_obj(self, obj):
        for field in self.fields:
            val = getattr(self, field[0])
            if hasattr(obj, field[0] + '_dbus'):
                setattr(obj, field[0] + '_dbus', val)
            else:
                setattr(obj, field[0], val)

    def __repr__(self):
        return "<%s:\n%s>" % (
            type(self).__name__,
            "\n".join(map(
                lambda field: '%s: %s' % (
                    field[0], str(getattr(self, field[0], '')),
                ), self.fields,
            ))
        )


class Note(DbusSendable):
    ORDER_TITLE = 0
    ORDER_UPDATED = 1
    ORDER_TITLE_DESC = 2
    ORDER_UPDATED_DESC = 3

    fields = (
        ('id', 'i'),
        ('title', 's'),
        ('content', 's'),
        ('created', 'x'),
        ('updated', 'x'),
        ('notebook', 'i'),
        ('tags', 'as'),
        ('place', 's'),
        ('pinnded', 'b'),
        ('conflict_parent', 'i'),
        ('conflict_items', 'ai'),
        ('share_date', 'i'),
        ('share_url', 's'),
    )


class Notebook(DbusSendable):
    fields = (
        ('id', 'i'),
        ('name', 's'),
        ('default', 'i'),
    )


class Tag(DbusSendable):
    fields = (
        ('id', 'i'),
        ('name', 's'),
    )


class Resource(DbusSendable):
    fields = (
        ('id', 'i'),
        ('file_name', 's'),
        ('file_path', 's'),
        ('mime', 's'),
        ('hash', 's'),
    )


class Place(DbusSendable):
    fields = (
        ('id', 'i'),
        ('name', 's'),
    )
