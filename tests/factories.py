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


def invoke_session(session):
    """Invoke sqlalchemy sessions"""
    for _factory in (
        NotebookFactory,
        TagFactory,
    ):
        _factory.FACTORY_SESSION = session
