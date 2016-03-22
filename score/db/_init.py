# Copyright © 2015 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

import sqlalchemy as sa
from score.init import (
    ConfiguredModule, parse_dotted_path, parse_bool, parse_call)
from zope.sqlalchemy import ZopeTransactionExtension
from ._session import sessionmaker
from ._sa_stmt import (
    DropInheritanceTrigger, CreateInheritanceTrigger,
    generate_create_inheritance_view_statement,
    generate_drop_inheritance_view_statement)


defaults = {
    'base': None,
    'destroyable': False,
    'ctx.member': 'db',
}


def init(confdict, ctx=None):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`sqlalchemy.*`
        All configuration values under this key will be passed to
        :func:`engine_from_config`, which in turn calls
        :func:`sqlalchemy.create_engine` with these configuration values as
        keyword arguments. Usually the following is sufficient::

            sqlalchemy.url = postgresql://dbuser@localhost/projname

    :confkey:`base` :faint:`[default=None]`
        The dotted python path to the :ref:`base class <db_base>` to
        configure. See :func:`parse_dotted_path` for the syntax.

    :confkey:`destroyable` :faint:`[default=False]`
        Whether destructive operations may be performed on the database. This
        value prevents accidental deletion of important data on live servers.

    :confkey:`ctx.member` :faint:`[default=db]`
        The name of the :term:`context member`, that should be registered with
        the configured :mod:`score.ctx` module (if there is one). The default
        value allows you to always access a valid session within a
        :class:`score.ctx.Context` like this:

        >>> ctx.db.query(User).first()

        Providing the special value 'None' will disable registration of the
        context member, even if a configured :mod:`ctx module <score.ctx>` was
        provided.

    This function will initialize an sqlalchemy
    :ref:`Engine <sqlalchemy:engines_toplevel>` and the provided
    :ref:`base class <db_base>`.

    """
    conf = defaults.copy()
    conf.update(confdict)
    engine = engine_from_config(conf)
    Base = None
    if 'base' in conf:
        Base = parse_dotted_path(conf['base'])
        Base.metadata.bind = engine
    ctx_member = None
    if ctx and conf['ctx.member'] not in (None, 'None'):
        ctx_member = conf['ctx.member']
    db_conf = ConfiguredDbModule(
        engine, Base, parse_bool(conf['destroyable']), ctx_member)
    if ctx_member:

        def constructor(ctx):
            zope_tx = ZopeTransactionExtension(
                transaction_manager=ctx.tx_manager)
            return db_conf.Session(extension=zope_tx)

        ctx.register(ctx_member, constructor)
    return db_conf


def engine_from_config(config):
    """
    A wrapper around :func:`sqlalchemy.engine_from_config`, that converts
    certain configuration values. Currently, the following configurations are
    processed:

    - ``sqlalchemy.echo`` (using :func:`score.init.parse_bool`)
    - ``sqlalchemy.echo_pool`` (using :func:`score.init.parse_bool`)
    - ``sqlalchemy.case_sensitive`` (using :func:`score.init.parse_bool`)
    - ``sqlalchemy.module`` (using :func:`score.init.parse_dotted_path`)
    - ``sqlalchemy.poolclass`` (using :func:`score.init.parse_dotted_path`)
    - ``sqlalchemy.pool`` (using :func:`score.init.parse_call`)
    - ``sqlalchemy.pool_size`` (converted to `int`)
    - ``sqlalchemy.pool_recycle`` (converted to `int`)
    """
    if 'sqlalchemy.echo' in config:
        config['sqlalchemy.echo'] = parse_bool(config['sqlalchemy.echo'])
    if 'sqlalchemy.echo_pool' in config:
        config['sqlalchemy.echo_pool'] = \
            parse_bool(config['sqlalchemy.echo_pool'])
    if 'sqlalchemy.case_sensitive' in config:
        config['sqlalchemy.case_sensitive'] = \
            parse_bool(config['sqlalchemy.case_sensitive'])
    if 'sqlalchemy.module' in config:
        config['sqlalchemy.module'] = \
            parse_dotted_path(config['sqlalchemy.module'])
    if 'sqlalchemy.poolclass' in config:
        config['sqlalchemy.poolclass'] = \
            parse_dotted_path(config['sqlalchemy.poolclass'])
    if 'sqlalchemy.pool' in config:
        config['sqlalchemy.pool'] = parse_call(config['sqlalchemy.pool'])
    if 'sqlalchemy.pool_size' in config:
        config['sqlalchemy.pool_size'] = \
            int(config['sqlalchemy.pool_size'])
    if 'sqlalchemy.pool_recycle' in config:
        config['sqlalchemy.pool_recycle'] = \
            int(config['sqlalchemy.pool_recycle'])
    return sa.engine_from_config(config)


class ConfiguredDbModule(ConfiguredModule):
    """
    This module's :class:`configuration class
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, engine, Base, destroyable, ctx_member):
        super().__init__(__package__)
        self.engine = engine
        self.Base = Base
        self.destroyable = destroyable
        self.ctx_member = ctx_member
        self.Session = sessionmaker(
            self, extension=ZopeTransactionExtension(), bind=engine)

    def create(self):
        """
        Generates all necessary tables, views, triggers, sequences, etc.
        """
        # create all tables
        self.Base.metadata.create_all()
        # generate inheritance views and triggers: we do this starting with the
        # base class and working our way down the inheritance hierarchy
        classes = [cls for cls in self.Base.__subclasses__()
                   if cls.__score_db__['parent'] is None]
        while classes:
            for cls in classes:
                self._create_inheritance_trigger(cls)
                self._create_inheritance_view(cls)
            classes = [sub for cls in classes for sub in cls.__subclasses__()]

    def _create_inheritance_trigger(self, class_):
        """
        Creates the inheritance trigger for given *class_*. This trigger will
        delete entries from parent tables, whenever a row in the given table is
        deleted.

        Example: assuming the given class ``Administrator`` is a sub-class of
        ``User``, this will create an sqlite trigger like the following:

            CREATE TRIGGER autodel_administrator
              AFTER DELETE ON _administrator
            FOR EACH ROW BEGIN
              DELETE FROM _user WHERE id = OLD.id;
            END
        """
        parent_tables = []
        parent = class_.__score_db__['parent']
        while parent:
            parent_tables.append(parent.__table__)
            parent = parent.__score_db__['parent']
        self.engine.execute(DropInheritanceTrigger(class_.__table__))
        if parent_tables:
            self.engine.execute(CreateInheritanceTrigger(
                class_.__table__, parent_tables[-1]))

    def _create_inheritance_view(self, class_):
        """
        Creates the inheritance view for given *class_*. The view combines all
        fields in the given class, as well as those in parent classes.

        Example: assuming the following table structure:

          CREATE TABLE _file (
            id INTEGER NOT NULL,
            name VARCHAR(100)
          );

          CREATE TABLE _image (
            id INTEGER NOT NULL,
            format VARCHAR(10),
            FOREIGN KEY(id) REFERENCES _file (id)
          );

        The inheritance view for the ``Image`` class would look like the
        following:

          CREATE VIEW image AS
          SELECT f.id, f.name, i.format
          FROM _file f INNER JOIN _image i ON f.id = i.id
        """
        dropview = generate_drop_inheritance_view_statement(class_)
        self.engine.execute(dropview)
        if class_.__score_db__['inheritance'] is not None:
            createview = generate_create_inheritance_view_statement(class_)
            self.engine.execute(createview)

    def destroy(self, session=None):
        """
        .. note::
            This function currently only works on postgresql and sqlite
            databases.

        Drops everything in the database – tables, views, sequences, etc.
        This function will not execute if the database configuration was not
        explicitly set to be *destroyable*.
        """
        assert self.destroyable
        if self.engine.dialect.name == 'postgresql':
            from .pg import destroy
        elif self.engine.dialect.name == 'sqlite':
            from .sqlite import destroy
        else:
            raise Exception('Can only destroy sqlite and postgresql databases')
        if session is None:
            session = self.Session()
        destroy(session, self.destroyable)
