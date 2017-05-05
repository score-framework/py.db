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


# This file has nothing to export, it just adds some operations to the alembic
# engine, it has to be executed, though. Since many python source checkers
# complain when importing * from a module, we provide a useless export variable:
_import_dummy = None

try:
    from alembic.operations import Operations, MigrateOperation
except ImportError:
    # No alembic installed, just skip this file as a whole
    pass
else:
    from ._sa_stmt import (
        generate_create_inheritance_view_statement,
        generate_drop_inheritance_view_statement)

    @Operations.register_operation("create_inheritance_view")
    class CreateInheritanceViewOp(MigrateOperation):
        """Create a View."""

        def __init__(self, db_class, schema=None):
            self.db_class = db_class
            self.schema = schema

        @classmethod
        def create_inheritance_view(cls, operations, db_class, **kw):
            op = CreateInheritanceViewOp(db_class, **kw)
            return operations.invoke(op)

        def reverse(self):
            # only needed to support autogenerate
            return DropInheritanceViewOp(self.sequence_name, schema=self.schema)

    @Operations.register_operation("drop_inheritance_view")
    class DropInheritanceViewOp(MigrateOperation):
        """Create a View."""

        def __init__(self, db_class, schema=None):
            self.db_class = db_class
            self.schema = schema

        @classmethod
        def drop_inheritance_view(cls, operations, db_class, **kw):
            op = DropInheritanceViewOp(db_class, **kw)
            return operations.invoke(op)

        def reverse(self):
            # only needed to support autogenerate
            return CreateInheritanceViewOp(self.sequence_name,
                                           schema=self.schema)

    @Operations.implementation_for(CreateInheritanceViewOp)
    def create_inheritance_view(operations, op):
        stmt = generate_create_inheritance_view_statement(op.db_class)
        operations.execute(stmt)

    @Operations.implementation_for(DropInheritanceViewOp)
    def drop_inheritance_view(operations, op):
        stmt = generate_drop_inheritance_view_statement(op.db_class)
        operations.execute(stmt)
