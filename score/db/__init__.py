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

from .helpers import *
from .dataloader import load_yaml, load_url, load_data, DataLoaderException
from .session import sessionmaker
from score.init import (
    ConfiguredModule, parse_dotted_path, parse_bool, parse_call)
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import String
from zope.sqlalchemy import ZopeTransactionExtension
from .dbenum import Enum
from .alembic import *
from ._sa_stmt import (
    DropInheritanceTrigger, CreateInheritanceTrigger,
    generate_create_inheritance_view_statement,
    generate_drop_inheritance_view_statement)


defaults = {
    'base': None,
    'destroyable': False,
    'ctx.member': 'db',
}


def init(confdict, ctx_conf=None):
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
    conf = dict(defaults.items())
    conf.update(confdict)
    if 'sqlalchemy.poolclass' in conf:
        conf['sqlalchemy.poolclass'] = \
            parse_dotted_path(conf['sqlalchemy.poolclass'])
    if 'sqlalchemy.pool' in conf:
        conf['sqlalchemy.pool'] = parse_call(conf['sqlalchemy.pool'])
    engine = engine_from_config(conf)
    Base = None
    if 'base' in conf:
        Base = parse_dotted_path(conf['base'])
        Base.metadata.bind = engine
    if ctx_conf:
        zope_tx = ZopeTransactionExtension(
            transaction_manager=ctx_conf.tx_manager)
    else:
        zope_tx = ZopeTransactionExtension()
    db_conf = ConfiguredDbModule(engine, Base, parse_bool(conf['destroyable']))
    db_conf.Session = sessionmaker(db_conf, extension=zope_tx, bind=engine)
    if ctx_conf and conf['ctx.member'] not in (None, 'None'):
        ctx_conf.register(conf['ctx.member'], lambda ctx: db_conf.Session())
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

    def __init__(self, engine, Base, destroyable):
        super().__init__(__package__)
        self.engine = engine
        self.Base = Base
        self.destroyable = destroyable

    def create(self):
        """
        Generates all necessary tables, views and sequences.
        """
        # This method could in theory be implemented by calling
        # self.Base.metadata.create_all()
        # In practice, though, SQLAlchemy might choos to create tables of
        # subclasses before their parent classes (observed on an sqlite
        # database), in which case our views and triggers would reference tables
        # which do not exist yet.
        # That's why we create the tables level by level, starting with those
        # that don't have a parent table and moving downward the hierarchy chain
        classes = [cls for cls in self.Base.__subclasses__()
                   if cls.__score_db__['parent'] is None]
        while classes:
            self.Base.metadata.create_all(
                tables=map(lambda cls: cls.__table__, classes))
            classes = [sub for cls in classes for sub in cls.__subclasses__()]
        # create remaining classes
        self.Base.metadata.create_all()

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


class ConfigurationError(Exception):
    pass


def create_base():
    """
    Returns a :ref:`base class <db_base>` for database access objects.
    """

    Base = None

    class _BaseMeta(DeclarativeMeta):
        """
        Metaclass for the created :class:`.Base` class.
        """

        def __init__(cls, classname, bases, attrs):
            """
            Normalizes configuration values of new database classes.
            """
            if Base is not None:
                _BaseMeta.set_config(cls, classname, bases, attrs)
                _BaseMeta.set_tablename(cls, classname, bases, attrs)
                _BaseMeta.configure_inheritance(cls, classname, bases, attrs)
                _BaseMeta.set_id(cls, classname, bases, attrs)
            DeclarativeMeta.__init__(cls, classname, bases, attrs)
            if Base is not None:
                event.listen(cls.__table__, "after_create", Base._after_create)

        def _after_create(self, target, connection, **kw):
            """
            Sqlalchemy event listener that creates all associated views and
            triggers after a table is created.
            """
            def find_class(cls, parent_tables):
                if cls.__table__ == target:
                    return cls, parent_tables
                parent_tables = parent_tables + [cls.__table__]
                for subclass in cls.__subclasses__():
                    result = find_class(subclass, parent_tables)
                    if result:
                        return result
            for subclass in Base.__subclasses__():
                result = find_class(subclass, [])
                if result:
                    break
            if not result:
                return
            class_, parent_tables = result
            dropview = generate_drop_inheritance_view_statement(class_)
            droptrigger = DropInheritanceTrigger(class_.__table__)
            if len(parent_tables) > 0:
                inheritancetrigger = CreateInheritanceTrigger(class_.__table__,
                                                              parent_tables[-1])
            connection.execute(dropview)
            connection.execute(droptrigger)
            if class_.__score_db__['inheritance'] is not None:
                createview = generate_create_inheritance_view_statement(class_)
                connection.execute(createview)
            if len(parent_tables) > 0:
                connection.execute(inheritancetrigger)

        def set_config(cls, classname, bases, attrs):
            """
            Sets the class' __score_db__ value with the computed configuration.
            This dict will contain the following values at the end of this
            function:

            - parent: the parent class in the inheritance hierarchy towards
              Base.
            - inheritance: the inheritance type
            - type_name: name of this type in the database, as stored in the
              type_column.
            - type_column: name of the column containing the type_name
            """
            cfg = {}
            if '__score_db__' in attrs:
                cfg = attrs['__score_db__']
            cfg['base'] = Base
            # determine base class
            cfg['parent'] = None
            for base in bases:
                if base != Base and issubclass(base, Base):
                    if cfg['parent'] is not None:
                        raise ConfigurationError(
                            'Multiple parent classes in %s' % classname)
                    cfg['parent'] = base
            parent = cfg['parent']
            # configure inheritance
            if parent is not None:
                # this is a sub-class of another class that should
                # already have the 'polymorphic_on' configuration.
                inheritance = parent.__score_db__['inheritance']
                if inheritance is None:
                    raise ConfigurationError(
                        'Parent table of %s does not support inheritance' %
                        classname)
                if 'inheritance' not in cfg:
                    cfg['inheritance'] = inheritance
                elif cfg['inheritance'] != inheritance:
                    raise ConfigurationError(
                        'Cannot change inheritance type of %s in subclass %s' %
                        (parent.__name__, classname))
            elif 'inheritance' not in cfg:
                cfg['inheritance'] = 'joined-table'
            else:
                valid = ('single-table', 'joined-table', None)
                if cfg['inheritance'] not in valid:
                    raise ConfigurationError(
                        'Invalid inheritance configuration "%s"' % cfg['inheritance'])
            # configure type_column
            if 'type_column' not in cfg:
                if '__mapper_args__' in attrs and 'polymorphic_on' in attrs['__mapper_args__']:
                    cfg['type_column'] = attrs['__mapper_args__']['polymorphic_on']
                else:
                    cfg['type_column'] = '_type'
            elif '__mapper_args__' in attrs and 'polymorphic_on' in attrs['__mapper_args__']:
                raise ConfigurationError(
                        'Both sqlalchemy and score.db configured with a type column,\n'
                        'please remove one of the two configurations in %s:\n'
                        ' - __mapper_args__[polymorphic_on]\n'
                        ' - __score_db__[type_column]' % classname)
            # configure type_name
            if 'type_name' not in cfg:
                if '__mapper_args__' in attrs and 'polymorphic_identity' in attrs['__mapper_args__']:
                    cfg['type_name'] = attrs['__mapper_args__']['polymorphic_identity']
                else:
                    cfg['type_name'] = cls2tbl(classname)[1:]
            elif '__mapper_args__' in attrs and 'polymorphic_identity' in attrs['__mapper_args__']:
                raise ConfigurationError(
                        'Both sqlalchemy and score.db configured with a polymorphic identity,\n'
                        'please remove one of the two configurations in %s:\n'
                        ' - __mapper_args__[polymorphic_identity]\n'
                        ' - __score_db__[type_name]' % classname)
            # done, assign result to class
            cls.__score_db__ = cfg

        def set_tablename(cls, classname, bases, attrs):
            """
            Sets the ``__tablename__`` member for sqlalchemy. Note that this
            value might be overridden with a manual declaration in the class.
            """
            if cls.__score_db__['inheritance'] == 'single-table' and \
                    cls.__score_db__['parent'] is not None:
                # this is a sub-class of another class that should
                # already have a __tablename__ attribute.
                return
            attrs['__tablename__'] = cls2tbl(classname)
            cls.__tablename__ = attrs['__tablename__']

        def configure_inheritance(cls, classname, bases, attrs):
            """
            Sets all necessary members to make the desired inheritance
            configuration work. Will set any/all of the following attributes,
            depending on the *inheritance* configuration:

            - cls.__mapper_args__
            - cls.__mapper_args__['polymorphic_identity']
            - cls.__mapper_args__['polymorphic_on']
            - cls._type
            """
            if cls.__score_db__['inheritance'] is None:
                return
            # define cls.__mapper_args__
            if '__mapper_args__' not in attrs:
                attrs['__mapper_args__'] = {}
                cls.__mapper_args__ = attrs['__mapper_args__']
            # define cls.__mapper_args__['polymorphic_identity']
            if 'polymorphic_identity' not in cls.__mapper_args__:
                cls.__mapper_args__['polymorphic_identity'] = cls.__score_db__['type_name']
            # define cls.__mapper_args__['polymorphic_on']
            if cls.__score_db__['parent'] is not None:
                # this is a sub-class of another class that should
                # already have the 'polymorphic_on' configuration.
                return
            cls.__mapper_args__['polymorphic_on'] = cls.__score_db__['type_column']
            # define the type column we're polymorphic on
            type_attr = cls.__mapper_args__['polymorphic_on']
            if type_attr not in attrs:
                attrs[type_attr] = Column(String(100), nullable=False)
                setattr(cls, type_attr, attrs[type_attr])

        def set_id(cls, classname, bases, attrs):
            """
            Generates the ``id`` column. The column will contain a foreign key
            constraint to parent class' table, if it is not a direct descendant
            of the :ref:`base class <db_base>`.
            """
            if cls.__score_db__['inheritance'] == 'single-table' and \
                    cls.__score_db__['parent'] is not None:
                return
            if hasattr(cls, '__mapper_args__') and 'primary_key' in cls.__mapper_args__:
                return
            args = [IdType]
            kwargs = {
                'primary_key': True,
                'nullable': False,
            }
            for base in bases:
                if base != Base and issubclass(base, Base):
                    args.append(ForeignKey('%s.id' % base.__tablename__))
                    break
            attrs['id'] = Column(*args, **kwargs)
            cls.id = attrs['id']

    Base = declarative_base(metaclass=_BaseMeta)
    return Base
