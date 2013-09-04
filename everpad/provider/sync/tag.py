from sqlalchemy.orm.exc import NoResultFound
from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.limits import constants as limits
from evernote.edam.type import ttypes
from ... import const
from ..exceptions import TTypeValidationFailed
from .. import models
from .base import BaseSync
import regex


class PushTag(BaseSync):
    """Push tags to server"""

    def push(self):
        """Push tags"""
        for tag in self.session.query(models.Tag).filter(
            models.Tag.action != const.ACTION_NONE,
        ):
            self.app.log('Pushing tag "%s" to remote server.' % tag.name)

            try:
                tag_ttype = self._create_ttype(tag)
            except TTypeValidationFailed:
                tag.action = const.ACTION_NONE
                self.app.log('tag %s skipped' % tag.name)
                continue

            if tag.action == const.ACTION_CREATE:
                self._push_new_tag(tag, tag_ttype)
            elif tag.action == const.ACTION_CHANGE:
                self._push_changed_tag(tag, tag_ttype)

        self.session.commit()

    def _create_ttype(self, tag):
        """Create tag ttype"""
        if not regex.search(limits.EDAM_TAG_NAME_REGEX, tag.name):
            raise TTypeValidationFailed()

        kwargs = dict(
            name=tag.name[:limits.EDAM_TAG_NAME_LEN_MAX].strip().encode('utf8'),
        )

        if tag.guid:
            kwargs['guid'] = tag.guid

        return ttypes.Tag(**kwargs)

    def _push_new_tag(self, tag, tag_ttype):
        """Push new tag"""
        try:
            tag_ttype = self.note_store.createTag(
                self.auth_token, tag_ttype,
            )
            tag.guid = tag_ttype.guid
            tag.action = const.ACTION_NONE
        except EDAMUserException as e:
            self.app.log(e)

    def _push_changed_tag(self, tag, tag_ttype):
        """Push changed tag"""
        try:
            self.note_store.updateTag(
                self.auth_token, tag_ttype,
            )
            tag.action = const.ACTION_NONE
        except EDAMUserException as e:
            self.app.log(e)


class PullTag(BaseSync):
    """Pull tags from server"""

    def __init__(self, *args, **kwargs):
        super(PullTag, self).__init__(*args, **kwargs)
        self._exists = []

    def pull(self):
        """Pull tags from server"""
        for tag_ttype in self.note_store.listTags(self.auth_token):
            self.app.log(
                'Pulling tag "%s" from remote server.' % tag_ttype.name)
            try:
                tag = self._update_tag(tag_ttype)
            except NoResultFound:
                tag = self._create_tag(tag_ttype)
            self._exists.append(tag.id)

        self.session.commit()
        self._remove_tags()

    def _create_tag(self, tag_ttype):
        """Create tag from server"""
        tag = models.Tag(guid=tag_ttype.guid)
        tag.from_api(tag_ttype)
        self.session.add(tag)
        self.session.commit()
        return tag

    def _update_tag(self, tag_ttype):
        """Update tag if exists"""
        tag = self.session.query(models.Tag).filter(
            models.Tag.guid == tag_ttype.guid,
        ).one()
        if tag.name != tag_ttype.name.decode('utf8'):
            tag.from_api(tag_ttype)
        return tag

    def _remove_tags(self):
        """Remove not exist tags"""
        if self._exists:
            q = (~models.Tag.id.in_(self._exists)
                & (models.Tag.action != const.ACTION_CREATE))
        else:
            q = (models.Tag.action != const.ACTION_CREATE)
        self.session.query(models.Tag).filter(q).delete(
            synchronize_session='fetch')
