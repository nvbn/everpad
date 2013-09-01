from everpad.provider import models
from everpad import const
from factory.alchemy import SQLAlchemyModelFactory
import factory


class NotebookFactory(SQLAlchemyModelFactory):
    """Note factory"""
    FACTORY_FOR = models.Notebook

    guid = factory.Sequence(lambda n: 'guid{}'.format(n))
    name = factory.Sequence(lambda n: 'name{}'.format(n))
    default = False
    service_created = factory.Sequence(lambda n: n)
    service_updated = factory.Sequence(lambda n: n)
    action = const.ACTION_NONE
    stack = ''


class TagFactory(SQLAlchemyModelFactory):
    """Tag factory"""
    FACTORY_FOR = models.Tag

    guid = factory.Sequence(lambda n: 'guid{}'.format(n))
    name = factory.Sequence(lambda n: 'name{}'.format(n))
    action = const.ACTION_NONE


class ResourceFactory(SQLAlchemyModelFactory):
    """Resource factory"""
    FACTORY_FOR = models.Resource

    guid = factory.Sequence(lambda n: 'guid{}'.format(n))
    hash = factory.Sequence(lambda n: 'hash{}'.format(n))
    mime = 'text/plain'
    action = const.ACTION_NONE


class NoteFactory(SQLAlchemyModelFactory):
    """Note factory"""
    FACTORY_FOR = models.Note

    guid = factory.Sequence(lambda n: 'guid{}'.format(n))
    title = factory.Sequence(lambda n: 'title{}'.format(n))
    content = factory.Sequence(lambda n: 'content{}'.format(n))
    created = factory.Sequence(lambda n: n)
    updated = factory.Sequence(lambda n: n)
    updated_local = factory.Sequence(lambda n: n)


class PlaceFactory(SQLAlchemyModelFactory):
    """Place factory"""
    FACTORY_FOR = models.Place

    name = factory.Sequence(lambda n: 'name{}'.format(n))


def invoke_session(session):
    """Invoke sqlalchemy sessions"""
    for _factory in (
        NotebookFactory,
        TagFactory,
        ResourceFactory,
        NoteFactory,
        PlaceFactory,
    ):
        _factory.FACTORY_SESSION = session
