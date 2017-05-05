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

from datetime import datetime
from sqlalchemy import Table, Column
from sqlalchemy.orm.session import Session as SASession
import sqlalchemy.orm as sa_orm


class IdNotFound(Exception):
    """
    Thrown by :meth:`.SessionMixin.by_ids` if one of the given ids was not
    found.
    """
    pass


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

    def by_ids(self, type, ids, *, order='_ids',
               yield_per=100, ignore_missing=True):
        """
        Yields objects of *type* with given *ids*. The parameter *yield_per*
        defines the chunk size of each database operation.

        If *ignore_missing* evaluates to `False`, the function will raise an
        IdNotFound exception if one of the ids were not present in the database.

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
        if ignore_missing:
            def test_missing(ids, objects):
                pass
        else:
            def test_missing(ids, result):
                if len(result) == len(ids):
                    return
                if isinstance(result, dict):
                    # most queries return a mapping of id to object, ...
                    found_ids = list(result.keys())
                else:
                    # ... while others just return a list of objects
                    found_ids = list(map(lambda o: o.id, result))
                first_missing = next(id for id in ids if id not in found_ids)
                raise IdNotFound(first_missing)
        if order is None:
            # unsorted, just return in random order.
            # note: we're not using sqlalchemy's Query.yield_per() here, since
            # we could then only detect missing ids after we produced the last
            # result chunk.
            while len(ids) > 0:
                chunk = ids[0:yield_per]
                ids = ids[yield_per:]
                objects = self.query(type).filter(type.id.in_(chunk)).all()
                test_missing(chunk, objects)
                yield from objects
            return
        if order == '_ids':
            # sorted by the ordering of the ids
            while len(ids) > 0:
                chunk = ids[0:yield_per]
                ids = ids[yield_per:]
                result = dict(self.query(type.id, type).
                              filter(type.id.in_(chunk)))
                test_missing(chunk, result)
                yield from (result[id] for id in chunk if id in result)
            return
        if len(ids) <= yield_per:
            # sort by something, but use a single query
            objects = self.query(type).\
                filter(type.id.in_(ids)).\
                order_by(order).\
                all()
            test_missing(ids, objects)
            yield from objects
            return
        # sort by something, and we have more ids than we can put in a single
        # query (yield_per > len(ids)).  create a temporary table as described
        # in the function documentation to sort the ids by the given *order* and
        # perform another query, returning the results in the ordering that we
        # just established (see last line of this function).
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
            if not ignore_missing and len(ids) != len(sorted_ids):
                first_missing = next(id for id in ids if id not in sorted_ids)
                raise IdNotFound(first_missing)
        return self.by_ids(type, sorted_ids, order='_id', yield_per=yield_per,
                           ignore_missing=ignore_missing)


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
