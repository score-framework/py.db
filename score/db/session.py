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

from datetime import datetime
from sqlalchemy import Table, Column
from sqlalchemy.orm.session import Session as SASession
import sqlalchemy.orm as sa_orm


class TemporaryTableCreator:
    """
    Helper class that wraps the creation and destruction of temporary tables
    within `with` blocks. There is no need to us this class directly, you can
    just use :meth:`.Session.mktmp`, instead.
    """

    def __init__(self, session, columns):
        self.session = session
        self.columns = columns
        self.table = None

    def __enter__(self):
        """
        Creates and returns the temporary table.
        """
        metadata = self.session.dbconf.Base.metadata
        name = 'tmp%d' % ((datetime.now().timestamp() * 1000) % 10**8)
        while name in metadata.tables:
            name = 'tmp%d' % ((datetime.now().timestamp() * 1000) % 10**8)
        name = 'temp.%s' % name
        self.table = Table(name, metadata, *self.columns)
        metadata.create_all(tables=[self.table])
        return self.table

    def __exit__(self, type, value, traceback):
        """
        Destroys the temporary table created during :meth:`__enter__`.
        """
        metadata = self.session.dbconf.Base.metadata
        metadata.drop_all(tables=[self.table])


class SessionMixin:
    """
    A mixin for sqlalchemy :class:`session <sqlalchemy.orm.session.Session>`
    classes that adds some convenience features.
    """

    def mktmp(self, columns):
        """
        Provides a scoped temporary table with provided *columns* definitions.
        Example usage::

            with session.mktmp([Column(Integer)]) as tmp_table:
                # the temporary table now exists in the database
                do_something(with=tmp_table)
            # the table is deleted automatically at this point

        """
        if not isinstance(columns, list):
            columns = list(columns)
        return TemporaryTableCreator(self, columns)

    def by_ids(self, type, ids, *, order='_ids', yield_per=100):
        """
        Yields objects of *type* with given *ids*. The parameter *yield_per*
        defines the chunk size of each database operation.

        By default, the function will return the objects in the order of their
        id in the *ids* parameter. The following code will print the User with
        id #4 first, followed by the users #2 and #5::

            for user in session.by_ids(User, [4,2,5]):
                print(user)

        It is possible to provide a different or ordering by passing an
        sqlalchemy expression as *order*::

            for user in session.by_ids(User, [4,2,5], order=User.name.desc()):
                # ...

        .. note::
            If you provide a custom *order*, and if there would be more than
            one database operation (i.e. if ``len(ids) > yield_per``), the
            function will create a temporary table for sorting the result. If
            you have enough memory, you might want to pass *yield_per* as
            ``len(ids)`` to avoid that.
        """
        if order is None:
            while len(ids) > 0:
                chunk = ids[0:yield_per]
                ids = ids[yield_per:]
                yield from self.query(type).filter(type.id.in_(chunk))
            return
        if order == '_ids':
            while len(ids) > 0:
                chunk = ids[0:yield_per]
                ids = ids[yield_per:]
                objects = dict(self.query(type.id, type).
                               filter(type.id.in_(chunk)))
                yield from (objects[id] for id in chunk)
            return
        if len(ids) < yield_per:
            objects = dict(self.query(type.id, type).filter(type.id.in_(ids)))
            yield from (objects[id] for id in ids)
            return
        tmpcols = [
            Column('id', type.id.property.columns[0].type, primary_key=True),
        ]
        with self.mktmp(tmpcols) as tmp:
            while len(ids) > 0:
                chunk = ids[0:yield_per]
                ids = ids[yield_per:]
                self.execute(tmp.insert(), map(lambda id: {'id': id}, chunk))
            sorted_ids = self.query(type.id).\
                join(tmp, onclause=(tmp.ref == type.id)).\
                order_by(order).\
                all()
        return self.by_ids(type, sorted_ids, yield_per=yield_per)


def sessionmaker(conf, *args, **kwargs):
    """
    Wrapper around sqlalchemy's :func:`sessionmaker
    <sqlalchemy.orm.sessionmaker>` that adds our :class:`.SessionMixin` to the
    session base class. All arguments — except the :class:`.DbConfiguration`
    *conf* — are passed to the wrapped ``sessionmaker`` function.
    """
    try:
        base = kwargs['class_']
    except KeyError:
        base = SASession

    class ConfiguredSession(base, SessionMixin):

        def __init__(self, *args, **kwargs):
            self.dbconf = conf
            base.__init__(self, *args, **kwargs)
            SessionMixin.__init__(self)

    kwargs['class_'] = ConfiguredSession
    return sa_orm.sessionmaker(*args, **kwargs)
