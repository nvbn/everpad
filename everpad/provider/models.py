from BeautifulSoup import BeautifulSoup
from sqlalchemy import Table, Column, Integer, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
from ..tools import prepare_file_path
from .. import const
import binascii
import os
import urllib
import json
import dbus
import socket


Base = declarative_base()


notetags_table = Table(
    'notetags', Base.metadata,
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
    updated_local = Column(Integer)
    notebook_id = Column(Integer, ForeignKey('notebooks.id'))
    notebook = relationship("Notebook", backref='note')
    tags = relationship(
        "Tag",
        secondary=notetags_table,
        backref="notes",
    )
    pinnded = Column(Boolean, default=False)
    resources = relationship("Resource")
    place_id = Column(Integer, ForeignKey('places.id'))
    place = relationship("Place", backref='note')
    action = Column(Integer)
    conflict_parent = relationship("Note", post_update=False)
    conflict_parent_id = Column(
        Integer, ForeignKey('notes.id'), nullable=True,
    )

    # sharing data:
    share_date = Column(Integer)
    share_status = Column(Integer, default=const.SHARE_NONE)
    share_url = Column(String)

    @property
    def tags_dbus(self):
        return map(lambda tag: tag.name, self.tags)

    @tags_dbus.setter
    def tags_dbus(self, val):
        tags = []
        for tag in val:
            if tag and tag != ' ':  # for blank array and other
                try:
                    tags.append(self.session.query(Tag).filter(
                        (Tag.name == tag)
                        & (Tag.action != const.ACTION_DELETE)
                    ).one())
                except NoResultFound:
                    tg = Tag(name=tag, action=const.ACTION_CREATE)
                    self.session.add(tg)
                    tags.append(tg)
        self.tags = tags

    @property
    def notebook_dbus(self):
        if self.notebook:
            return self.notebook.id
        else:
            return self.session.query(Notebook).filter(
                Notebook.default == True,
            ).one().id

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

    @property
    def place_dbus(self):
        if self.place:
            return self.place.name
        return ''

    @place_dbus.setter
    def place_dbus(self, val):
        if val:
            self.set_place(val, self.session)

    @property
    def conflict_parent_dbus(self):
        if self.conflict_parent_id:
            return self.conflict_parent_id
        return 0

    @conflict_parent_dbus.setter
    def conflict_parent_dbus(self, val):
        pass

    @property
    def conflict_items_dbus(self):
        return map(
            lambda item: item.id,
            self.session.query(Note).filter(
                Note.conflict_parent_id == self.id,
            ).all(),
        ) or dbus.Array([], signature='i')

    @conflict_items_dbus.setter
    def conflict_items_dbus(self, val):
        pass

    @property
    def share_date_dbus(self):
        return self.share_date or 0

    @share_date_dbus.setter
    def share_date_dbus(self, val):
        pass

    @property
    def share_url_dbus(self):
        return self.share_url or ''

    @share_url_dbus.setter
    def share_url_dbus(self, val):
        pass

    def from_api(self, note, session):
        """Fill data from api"""
        soup = BeautifulSoup(note.content.decode('utf8'))
        content = reduce(
            lambda txt, cur: txt + unicode(cur),
            soup.find('en-note').contents, u'',
        )
        self.title = note.title.decode('utf8')
        self.content = content
        self.created = note.created
        self.updated = note.updated
        self.action = const.ACTION_NONE
        if note.notebookGuid:
            self.notebook = session.query(Notebook).filter(
                Notebook.guid == note.notebookGuid,
            ).one()
        if note.tagGuids:
            self.tags = session.query(Tag).filter(
                Tag.guid.in_(note.tagGuids),
            ).all()
        place_name = None
        if getattr(note, 'attributes'):
            if note.attributes.placeName:
                place_name = note.attributes.placeName.decode('utf8')
            elif note.attributes.longitude:
                try:
                    data = json.loads(urllib.urlopen(
                        'http://maps.googleapis.com/maps/api/geocode/json?latlng=%.4f,%.4f&sensor=false' % (
                            note.attributes.latitude,
                            note.attributes.longitude,
                        ),
                    ).read())
                    try:
                        place_name = data['results'][0]['formatted_address']
                    except (IndexError, KeyError):
                        pass
                except socket.error:
                    pass
        if place_name:
            self.set_place(place_name, session)

    def set_place(self, name, session):
        try:
            place = session.query(Place).filter(
                Place.name == name,
            ).one()
        except NoResultFound:
            place = Place(name=name)
            session.add(place)
        self.place = place


class Notebook(Base):
    __tablename__ = 'notebooks'
    id = Column(Integer, primary_key=True)
    guid = Column(String)
    name = Column(String)
    default = Column(Boolean)
    service_created = Column(Integer)
    service_updated = Column(Integer)
    action = Column(Integer)
    stack = Column(String)

    def from_api(self, notebook):
        """Fill data from api"""
        self.name = notebook.name.decode('utf8')
        self.default = notebook.defaultNotebook
        self.service_created = notebook.serviceCreated
        self.service_updated = notebook.serviceUpdated
        self.action = const.ACTION_NONE
        if notebook.stack:
            self.stack = notebook.stack.decode('utf8')

    @property
    def stack_dbus(self):
        if self.stack:
            return self.stack
        return ''

    @stack_dbus.setter
    def stack_dbus(self, val):
        self.stack = val


class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    guid = Column(String)
    name = Column(String)
    action = Column(Integer)

    def from_api(self, tag):
        """Fill data from api"""
        self.name = tag.name.decode('utf8')
        self.action = const.ACTION_NONE


class Resource(Base):
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey('notes.id'))
    file_name = Column(String)
    file_path = Column(String)
    guid = Column(String)
    hash = Column(String)
    mime = Column(String)
    action = Column(Integer)

    def from_api(self, resource):
        """Fill data from api"""
        if resource.attributes.fileName:
            self.file_name = resource.attributes.fileName.decode('utf8')
        else:
            self.file_name = resource.guid.decode('utf8')
        self.hash = binascii.b2a_hex(resource.data.bodyHash)
        self.action = const.ACTION_NONE
        self.mime = resource.mime.decode('utf8')
        path = os.path.expanduser('~/.everpad/data/%s/' % self.note_id)
        try:
            os.mkdir(path)
        except OSError:
            pass
        self.file_path = prepare_file_path(path, self.file_name)
        with open(self.file_path, 'w') as data:
            data.write(resource.data.body)


class Place(Base):
    __tablename__ = 'places'
    id = Column(Integer, primary_key=True)
    name = Column(String)


class Sync(Base):
    __tablename__ = 'sync'
    id = Column(Integer, primary_key=True)
    update_count = Column(Integer)
    last_sync = Column(Integer)
