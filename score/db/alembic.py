from ._sa_stmt import (
    generate_create_inheritance_view_statement,
    generate_drop_inheritance_view_statement)

try:
    from alembic.operations import Operations, MigrateOperation
except ImportError:

    class Operations:
        def register_operation(self, *args, **kwargs):
            pass

    class MigrateOperation:
        pass


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
        return CreateInheritanceViewOp(self.sequence_name, schema=self.schema)


@Operations.implementation_for(CreateInheritanceViewOp)
def create_inheritance_view(operations, op):
    stmt = generate_create_inheritance_view_statement(op.db_class)
    operations.execute(stmt)


@Operations.implementation_for(DropInheritanceViewOp)
def drop_inheritance_view(operations, op):
    stmt = generate_drop_inheritance_view_statement(op.db_class)
    operations.execute(stmt)
