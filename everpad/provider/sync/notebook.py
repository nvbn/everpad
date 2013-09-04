from sqlalchemy.orm.exc import NoResultFound
from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.limits import constants as limits
from evernote.edam.type import ttypes
from ... import const
from ..exceptions import TTypeValidationFailed
from .. import models
from .base import BaseSync
import regex


class PushNotebook(BaseSync):
    """Notebook sync"""

    def push(self):
        """Push notebook changes to server"""
        for notebook in self.session.query(models.Notebook).filter(
            models.Notebook.action != const.ACTION_NONE,
        ):
            self.app.log(
                'Pushing notebook "%s" to remote server.' % notebook.name)

            try:
                notebook_ttype = self._create_ttype(notebook)
            except TTypeValidationFailed:
                self.app.log('notebook %s skipped' % notebook.name)
                notebook.action = const.ACTION_NONE
                continue

            if notebook.action == const.ACTION_CREATE:
                self._push_new_notebook(notebook, notebook_ttype)
            elif notebook.action == const.ACTION_CHANGE:
                self._push_changed_notebook(notebook, notebook_ttype)

        self.session.commit()
        self._merge_duplicates()

    def _create_ttype(self, notebook):
        """Create notebook ttype"""
        kwargs = dict(
            name=notebook.name[
                :limits.EDAM_NOTEBOOK_NAME_LEN_MAX
            ].strip().encode('utf8'),
            defaultNotebook=notebook.default,
        )

        if notebook.stack:
            kwargs['stack'] = notebook.stack[
                :limits.EDAM_NOTEBOOK_STACK_LEN_MAX
            ].strip().encode('utf8')

        if not regex.search(limits.EDAM_NOTEBOOK_NAME_REGEX, notebook.name):
            raise TTypeValidationFailed()

        if notebook.guid:
            kwargs['guid'] = notebook.guid

        return ttypes.Notebook(**kwargs)

    def _push_new_notebook(self, notebook, notebook_ttype):
        """Push new notebook to server"""
        try:
            notebook_ttype = self.note_store.createNotebook(
                self.auth_token, notebook_ttype,
            )
            notebook.guid = notebook_ttype.guid
            notebook.action = const.ACTION_NONE
        except EDAMUserException:
            notebook.action = const.ACTION_DUPLICATE
            self.app.log('Duplicate %s' % notebook_ttype.name)

    def _push_changed_notebook(self, notebook, notebook_ttype):
        """Push changed notebook"""
        try:
            notebook_ttype = self.note_store.updateNotebook(
                self.auth_token, notebook_ttype,
            )
            notebook.action = const.ACTION_NONE
        except EDAMUserException:
            notebook.action = const.ACTION_DUPLICATE
            self.app.log('Duplicate %s' % notebook_ttype.name)

    def _merge_duplicates(self):
        """Merge and remove duplicates"""
        for notebook in self.session.query(models.Notebook).filter(
            models.Notebook.action == const.ACTION_DUPLICATE,
        ):
            try:
                original = self.session.query(models.Notebook).filter(
                    (models.Notebook.action != const.ACTION_DUPLICATE)
                    & (models.Notebook.name == notebook.name)
                ).one()
            except NoResultFound:
                original = self.session.query(models.Notebook).filter(
                    models.Notebook.default == True,
                ).one()

            for note in self.session.query(models.Note).filter(
                models.Note.notebook_id == notebook.id,
            ):
                note.notebook = original

            self.session.delete(notebook)
        self.session.commit()


class PullNotebook(BaseSync):
    """Pull notebook from server"""

    def __init__(self, *args, **kwargs):
        super(PullNotebook, self).__init__(*args, **kwargs)
        self._exists = []

    def pull(self):
        """Receive notebooks from server"""
        for notebook_ttype in self.note_store.listNotebooks(self.auth_token):
            self.app.log(
                'Pulling notebook "%s" from remote server.' % notebook_ttype.name)
            try:
                notebook = self._update_notebook(notebook_ttype)
            except NoResultFound:
                notebook = self._create_notebook(notebook_ttype)
            self._exists.append(notebook.id)

        self.session.commit()
        self._remove_notebooks()

    def _create_notebook(self, notebook_ttype):
        """Create notebook from ttype"""
        notebook = models.Notebook(guid=notebook_ttype.guid)
        notebook.from_api(notebook_ttype)
        self.session.add(notebook)
        self.session.commit()
        return notebook

    def _update_notebook(self, notebook_ttype):
        """Try to update notebook from ttype"""
        notebook = self.session.query(models.Notebook).filter(
            models.Notebook.guid == notebook_ttype.guid,
        ).one()
        if notebook.service_updated < notebook_ttype.serviceUpdated:
            notebook.from_api(notebook_ttype)
        return notebook

    def _remove_notebooks(self):
        """Remove not received notebooks"""
        if self._exists:
            q = (~models.Notebook.id.in_(self._exists)
                & (models.Notebook.action != const.ACTION_CREATE)
                & (models.Notebook.action != const.ACTION_CHANGE))
        else:
            q = ((models.Notebook.action != const.ACTION_CREATE)
                & (models.Notebook.action != const.ACTION_CHANGE))

        self.session.query(models.Notebook).filter(
            q).delete(synchronize_session='fetch')
