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

    @classmethod
    def from_obj(cls, data):
        inst = cls()
        for field in cls.fields:
            if hasattr(data, field[0] + '_dbus'):
                val = getattr(data, field[0] + '_dbus')
            else:
                val = getattr(data, field[0])
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
            result.append(getattr(self, field[0]))
        return tuple(result)

    def give_to_obj(self, obj):
        for field in self.fields:
            val = getattr(self, field[0])
            if hasattr(obj, field[0] + '_dbus'):
                setattr(obj, field[0] + '_dbus', val)
            else:
                setattr(obj, field[0], val)

    
class Note(DbusSendable):
    fields = (
        ('id', 'i'),
        ('title', 's'),
        ('content', 's'),
        ('created', 'i'),
        ('updated', 'i'),
        ('notebook', 'i'),
        ('tags', 'as'),
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
