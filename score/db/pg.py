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

"""
Provides functions specific to PostgreSQL databases.
"""

import configparser
from score.db import DropInheritanceTrigger, CreateInheritanceTrigger, DropView, CreateView
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.exc import StatementError
import transaction
from zope.sqlalchemy import mark_changed

import logging
log = logging.getLogger(__name__)


def list_views(session):
    """
    Returns a list of view names from the current database's public schema.
    """
    sql = "SELECT table_name FROM information_schema.tables "\
        "WHERE table_schema='public' AND table_type='VIEW'"
    return [name for (name, ) in session.execute(sql)]


def list_tables(session):
    """
    Returns a list of table names from the current database's public schema.
    """
    sql = "SELECT table_name FROM information_schema.tables "\
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    return [name for (name, ) in session.execute(sql)]


def list_sequences(session):
    """
    Returns a list of the sequence names from the current
    database's public schema.
    """
    sql = "SELECT sequence_name FROM information_schema.sequences "\
        "WHERE sequence_schema='public'"
    return [name for (name, ) in session.execute(sql)]

def list_enum_types(session):
    """
    Returns a list of enum type names from the current database.
    """
    sql = "SELECT typname FROM pg_type WHERE typtype = 'e'"
    return [name for (name, ) in session.execute(sql)]


def destroy(session, destroyable):
    """
    Drops everything in the database – tables, views, sequences, etc. For
    safety reasons, the *destroyable* flag of the database
    :class:`configuration <score.db.DbConfiguration>` must be passed as a
    parameter.
    """
    assert destroyable
    with transaction.manager:
        for seq in list_sequences(session):
            session.execute('DROP SEQUENCE "%s" CASCADE' % seq)
        for view in list_views(session):
            session.execute('DROP VIEW "%s" CASCADE' % view)
        for table in list_tables(session):
            session.execute('DROP TABLE "%s" CASCADE' % table)
        for enum_type in list_enum_types(session):
            session.execute('DROP TYPE "%s" CASCADE' % enum_type)
        mark_changed(session)


@compiles(DropInheritanceTrigger, 'postgresql')
def visit_drop_inheritance_trigger(element, compiler, **kw):
    return "DROP TRIGGER IF EXISTS autodel%s ON %s" % (element.table.name, element.table.name)

@compiles(CreateInheritanceTrigger, 'postgresql')
def visit_create_inheritance_trigger(element, compiler, **kw):
    statement = ""
    statement += "CREATE OR REPLACE FUNCTION autodel%s() RETURNS TRIGGER AS $_$\n" % element.parent.name
    statement += "    BEGIN\n"
    statement += "        DELETE FROM %s WHERE id = OLD.id;\n" % element.parent.name
    statement += "        RETURN OLD;\n"
    statement += "    END $_$ LANGUAGE 'plpgsql';\n"
    statement += "CREATE TRIGGER autodel%s AFTER DELETE ON %s\n" % (element.table.name, element.table.name)
    statement += "FOR EACH ROW EXECUTE PROCEDURE autodel%s();\n" % element.parent.name
    return statement

@compiles(DropView, 'postgresql')
def visit_drop_view(element, compiler, **kw):
    return 'DROP VIEW IF EXISTS "%s"' % element.name

@compiles(CreateView, 'postgresql')
def visit_create_view(element, compiler, **kw):
    return 'CREATE VIEW "%s" AS %s' % (
         element.name,
         compiler.process(element.select, literal_binds=True)
     )

