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


def list_tables(session):
    """
    Returns a list of all table names.
    """
    sql = "SELECT name FROM sqlite_master WHERE type = 'table'"
    return [name for (name, ) in session.execute(sql)]


def list_views(session):
    """
    Returns a list of all view names.
    """
    sql = "SELECT name FROM sqlite_master WHERE type = 'view'"
    return [name for (name, ) in session.execute(sql)]


def list_triggers(session):
    """
    Returns a list of all trigger names.
    """
    sql = "SELECT name FROM sqlite_master WHERE type = 'trigger'"
    return [name for (name, ) in session.execute(sql)]


def destroy(session, destroyable):
    """
    Drops everything in the database – tables, views, sequences, etc. For
    safety reasons, the *destroyable* flag of the database
    :class:`configuration <score.db.DbConfiguration>` must be passed as a
    parameter.
    """
    assert destroyable
    session.execute("PRAGMA foreign_keys=OFF")
    for trigger in list_triggers(session):
        session.execute('DROP TRIGGER "%s"' % trigger)
    for view in list_views(session):
        session.execute('DROP VIEW "%s"' % view)
    for table in list_tables(session):
        session.execute('DROP TABLE "%s"' % table)
    session.execute("VACUUM")
    session.execute("PRAGMA foreign_keys=ON")
