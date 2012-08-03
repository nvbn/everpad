from sqlalchemy import Table, Column, Integer, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
from BeautifulSoup import BeautifulSoup

Base = declarative_base()


ACTION_NONE = 0
ACTION_CREATE = 1
ACTION_DELETE = 2
ACTION_CHANGE = 3


notetags_table = Table('notetags', Base.metadata,
    Column('note', Integer, ForeignKey('notes.id')),
    Column('tag', Integer, ForeignKey('tags.id'))
)


class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    guid = Column(String)
    title = Column(String)
    content = Column(String)
    created = Column(Integer)
    updated = Column(Integer)
    notebook_id = Column(Integer, ForeignKey('notebooks.id'))
    notebook = relationship("Notebook", backref='note')
    tags = relationship("Tag",
        secondary=notetags_table,
        backref="notes",
    )
    action = Column(Integer)

    @property
    def tags_dbus(self):
        return map(lambda tag: tag.name, self.tags)

    @tags_dbus.setter
    def tags_dbus(self, val):
        tags = []
        for tag in val:
            try:
                tags.append(self.session.query(Tag).filter(
                    Tag.name == tag,
                ).one()) # shit shit shit
            except NoResultFound:
                tg = Tag(name=tag)
                self.session.add(tg)
                tags.append(tg)
        self.tags = tags

    @property
    def notebook_dbus(self):
        if self.notebook:
            return self.notebook.id
        return

    @notebook_dbus.setter
    def notebook_dbus(self, val):
        try:
            self.notebook = self.session.query(Notebook).filter(
                Notebook.id == val,
            ).one()
        except NoResultFound:
            self.notebook = self.session.query(Notebook).filter(
                Notebook.default == True,
            ).one()

    def from_api(self, note, query):
        """Fill data from api"""
        soup = BeautifulSoup(note.content.decode('utf8'))
        content = ''.join(map(   # shit =)
            lambda tag: unicode(tag),
            soup.find('en-note').fetch(),
        ))
        self.title = note.title.decode('utf8')
        self.content = content
        self.created = note.created
        self.updated = note.updated
        self.action = ACTION_NONE
        if note.notebookGuid:
            self.notebook = query(Notebook).filter(
                Notebook.guid == note.notebookGuid,
            ).one()
        if note.tagGuids:
            self.tags = query(Tag).filter(
                Tag.guid.in_(note.tagGuids),
            ).all()


class Notebook(Base):
    __tablename__ = 'notebooks'
    id = Column(Integer, primary_key=True)
    guid = Column(String)
    name = Column(String)
    default = Column(Boolean)
    service_created = Column(Integer)
    service_updated = Column(Integer)
    action = Column(Integer)

    def from_api(self, notebook):
        """Fill data from api"""
        self.name = notebook.name.decode('utf8')
        self.default = notebook.defaultNotebook
        self.service_created = notebook.serviceCreated
        self.service_updated = notebook.serviceUpdated
        self.action = ACTION_NONE


class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    guid = Column(String)
    name = Column(String)
    action = Column(Integer)

    def from_api(self, tag):
        """Fill data from api"""
        self.name = tag.name.decode('utf8')
        self.action = ACTION_NONE
