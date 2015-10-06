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

import re
from sqlalchemy import Column, ForeignKey, BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import backref, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.orderinglist import ordering_list


IdType = BigInteger()
IdType = IdType.with_variant(Integer, 'sqlite')


# taken from stackoverflow:
# http://stackoverflow.com/a/1176023/44562
_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')
def cls2tbl(cls):
    """
    Converts a class (or a class name) to a table name. The class name is
    expected to be in *CamelCase*. The return value will be
    *seperated_by_underscores* and prefixed with an underscore. Omitting
    the underscore will yield the name of the class's :ref:`view <db_view>`.
    """
    if isinstance(cls, type):
        cls = cls.__name__
    s1 = _first_cap_re.sub(r'\1_\2', cls)
    return '_' + _all_cap_re.sub(r'\1_\2', s1).lower()


def tbl2cls(tbl):
    """
    Inverse of :func:`.cls2tbl`. Returns the name of a class.
    """
    if tbl[0] == '_':
        tbl = tbl[1:]
    parts = tbl.split('_')
    return ''.join(map(lambda s: s.capitalize(), parts))


def create_relationship_class(cls1, cls2, member, *,
                              sorted=False, duplicates=True, backref=None):
    """
    Creates a class linking two given models and adds appropriate relationship
    properties to the classes.

    At its minimum, this function requires two classes *cls1* and *cls2* to be
    linked—where cls1 is assumed to be the owning part of the relation—and the
    name of the member to be added to the owning class:

    >>> UserGroup = create_relationship_class(User, Group, 'groups')

    This will create a class called UserGroup, which looks like the following:

    >>> class UserGroup(Storable):
    ...     __score_db__: {
    ...         'inheritance': None
    ...     }
    ...     index = Column(Integer, nullable=False)
    ...     user_id = Column(IdType, nullable=False, ForeignKey('_user.id'))
    ...     user = relationship(Group, foreign_keys=[user_id])
    ...     group_id = Column(IdType, nullable=False, ForeignKey('_group.id'))
    ...     group = relationship(Group, foreign_keys=[group_id])

    It will also add a new member 'groups' to the User class, which is of type
    :class:`sqlalchemy.orm.properties.RelationshipProperty`.

    The parameter *sorted* decides whether the relationship is stored with a
    sorting 'index' column.

    It is possible to declare that the relationship does not accept
    *duplicates*, in which case the table will also have a
    :class:`UniqueConstraint <sqlalchemy.schema.UniqueConstraint>` on
    ``[user_id, group_id]``

    Providing a *backref* member, will also add a relationship property to the
    second class with the given name.

    """
    name = cls1.__name__ + cls2.__name__
    idcol1 = cls1.__tablename__[1:] + '_id'
    idcol2 = cls2.__tablename__[1:] + '_id'
    refcol1 = cls1.__tablename__[1:]
    refcol2 = cls2.__tablename__[1:]
    members = {
        '__score_db__': {
            'inheritance': None
        },
        idcol1: Column(IdType, ForeignKey('%s.id' % cls1.__tablename__),
                       nullable=False),
        idcol2: Column(IdType, ForeignKey('%s.id' % cls2.__tablename__),
                       nullable=False),
    }
    members[refcol1] = relationship(cls1, foreign_keys=members[idcol1])
    members[refcol2] = relationship(cls2, foreign_keys=members[idcol2])
    if not duplicates:
        members['__mapper_args__'] = {
            'primary_key': [members[idcol1], members[idcol2]]
        }
    if sorted:
        members['index'] = Column(Integer, nullable=False)
    cls = type(name, (cls1.__score_db__['base'],), members)
    if sorted:
        rel = relationship(cls2, secondary=cls.__tablename__,
                           order_by='%s.index' % cls.__name__)
    else:
        rel = relationship(cls2, secondary=cls.__tablename__)
    setattr(cls1, member, rel)
    if backref:
        rel = relationship(cls1, secondary=cls.__tablename__)
        setattr(cls2, backref, rel)
    return cls


def create_collection_class(owner, member, column, *,
                            sorted=True, duplicates=True):
    """
    Creates a class for holding the values of a collection in given *owner*
    class.

    The given *owner* class will be updated to have a new *member* with given
    name, which is a list containing elements as described by *column*:

    >>> create_collection_class(Group, 'permissions',
    ...                         Column(PermissionEnum.db_type(), nullable=False)

    Group objects will now have a member called 'permissions', which contain a
    sorted list of PermissionEnum values.

    See :func:`.create_relationship_class` for the description of the keyword
    arguments.
    """
    name = owner.__name__ + tbl2cls(member)
    if sorted:
        bref = backref(member + '_wrapper', order_by='%s.index' % name,
                       collection_class=ordering_list('index'))
    else:
        bref = backref(member + '_wrapper')
    members = {
        '__score_db__': {
            'inheritance': None
        },
        'owner_id': Column(IdType, ForeignKey('%s.id' % owner.__tablename__),
                           nullable=False),
        'owner': relationship(owner, backref=bref),
        'value': column,
    }
    if sorted:
        members['index'] = Column(Integer, nullable=False)
    if not duplicates:
        members['__table_args__'] = (
            UniqueConstraint(members['owner_id'], column),
        )
    cls = type(name, (owner.__score_db__['base'],), members)
    proxy = association_proxy(member + '_wrapper', 'value',
                              creator=lambda v: cls(value=v))
    setattr(owner, member, proxy)
    return cls
