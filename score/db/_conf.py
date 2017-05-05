# Copyright © 2015-2017 STRG.AT GmbH, Vienna, Austria
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

from .helpers import IdType, cls2tbl
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.api import DeclarativeMeta


class ConfigurationError(Exception):
    pass


def create_base():
    """
    Returns a :ref:`base class <db_base_class>` for database access objects.
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
                attrs[type_attr] = sa.Column(sa.String(100), nullable=False)
                setattr(cls, type_attr, attrs[type_attr])

        def set_id(cls, classname, bases, attrs):
            """
            Generates the ``id`` column. The column will contain a foreign key
            constraint to parent class' table, if it is not a direct descendant
            of the :ref:`base class <db_base_class>`.
            """
            if cls.__score_db__['inheritance'] == 'single-table' and \
                    cls.__score_db__['parent'] is not None:
                return
            try:
                cls.__mapper_args__['primary_key']
                # primary key already configured via mapper, nothing to do here
                return
            except (AttributeError, KeyError):
                pass
            args = [IdType]
            kwargs = {
                'primary_key': True,
                'nullable': False,
            }
            for base in bases:
                if base != Base and issubclass(base, Base):
                    args.append(sa.ForeignKey('%s.id' % base.__tablename__))
                    break
            attrs['id'] = sa.Column(*args, **kwargs)
            cls.id = attrs['id']

    Base = declarative_base(metaclass=_BaseMeta)
    return Base
