.. module:: score.db
.. role:: faint
.. role:: confkey

********
score.db
********

This module provides functions and classes that implement our database
standards and provides helper functions for automating various operations.
We are using SQLAlchemy_ as our database connectivity and ORM_ layer.


Quickstart
==========

Create a :ref:`base class <db_base_class>`:

.. code-block:: python

    from score.db import create_base

    Storable = create_base()

All persistable classes should derive from this class, they will now
automatically receive an ``id`` column and a ``__tablename__`` declaration. The
only thing left to do is to add Columns:

.. code-block:: python

    from .storable import Storable
    from sqlalchemy import Column, String

    class User(Storable):
        username = Column(String(100), nullable=False)


The module will take care of inheritance mapping, too:

.. code-block:: python

    from .user import User
    from sqlalchemy import Column, Boolean


    class Blogger(User):
        may_publish = Column(Boolean, nullable=False, default=True)


You can then create your database by calling
:meth:`score.db.ConfiguredDbModule.create`.

>>> from score.init import init_from_file
>>> score = init_from_file('local.conf')
>>> score.db.create()

If you are using the :mod:`score.ctx` module, you can always access a
:class:`session <sqlalchemy.orm.session.Session>` bound to the context object's
transaction:

>>> ctx.db.query(db.User).get(1)
<User: sirlancelot>


Configuration
=============

.. autofunction:: score.db.init


Details
=======

One of the aims of this module is to establish some sane defaults for the
database configuration, so the early development within a project can focus on
the actual, project-specific challenges.

These features should describe all conventions upheld by this module to help
understand which shortcuts were taken to ensure an out-of-the-box fast and
robust development environment.


.. _db_base_class:

Base Class
----------

Database classes should derive from a base class constructed by a call to
:func:`score.db.create_base`. The class will automatically determine a table
name and automatically establish an ``id`` and a ``_type`` column. The
following class will be assigned the table name ``_user`` (as returned by
:func:`.cls2tbl`) and its id column as primary key:

.. code-block:: python
    :linenos:

    from score.db import create_base

    Storable = create_base()

    class User(Storable):
        pass


Sqlalchemy Defaults
-------------------

The :ref:`base class <db_base_class>` will set some class attributes automatically.
Most of the values shown here assume that the default :ref:`inheritance
configuration <db_inheritance>`—joined-table inheritance—is used:

- A **__tablename__** attribute that is determined using :func:`.cls2tbl`. A
  class called ``AdminUser`` would thus be translated to the table name
  ``_admin_user``. The reason for the leading underscore is that the name
  without that prefix is reserved for the database :ref:`VIEW <db_view>` aggregating all
  parent tables.

- An **id** column. This would look something like this, if it were written
  explicitly in a class:

    .. code-block:: python

        from score.db import create_base, IdType
        from sqlalchemy import Column

        Storable = create_base()

        class User(Storable):
            id = Column(IdType, nullable=False, primary_key=True)

        class AdminUser(User):
            id = Column(IdType, ForeignKey('_user.id'),
                        nullable=False, primary_key=True)

- A **_type** column storing the concrete type of a table entry. This allows
  sqlalchemy to determine which particular python class to use for an entry in
  the database:

    .. code-block:: python

        admin = AdminUser()
        session.add(admin)
        result = session.query(User).filter(User.id == admin.id).first()
        assert isinstance(result, AdminUser)

  In the example above, we received an object of the correct type
  ``AdminUser`` at the end, although we were actually querying for ``User``
  objects. Sqlalchemy was able to determine which class to use by looking up
  the ``_type`` value in the database.


All of these values can be overridden manually within the class declaration.
If you want your _type column to be an enumeration, for example, you can set
it manually:

    .. code-block:: python

        from score.db import create_base
        from sqlalchemy import Column, Enum

        Storable = create_base()

        class User(Storable):
            _type = Column(Enum('user', 'admin_user'), nullable=False)


.. _db_id_type:

Flexible ID Type
----------------

The module provides an sqlalchemy type to use for referencing other tables. The
primary reason for this feature is a work-around of a limitation of SQLite: it
only supports Integer fields as auto-incrementing ids. All other databases use
the much larger BigInteger.

This means that the preferred way of referencing objets is the following:

.. code-block:: python
    :emphasize-lines: 8

    from score.db import IdType
    from sqlalchemy import Column

    class User(Base):
        pass

    class Article(Base):
        user_id = Column(IdType, ForeignKey('_user.id'), nullable=False)


.. _db_inheritance:

Inheritance
-----------

Sqlalchemy_ supports various ways of configuring the inheritance in the
database. The full list of options can be found in :ref:`sqlalchemy's
documentation on inheritance mapping <sqlalchemy:inheritance_toplevel>`. But
since we value programmer time over CPU time and want to avoid unnecessery
optimization attempts at the early stages of a project, we would rather
recommend just using joined table inheritance at the beginning — which is also
the default in our framework:

.. code-block:: python
    :linenos:

    from score.db import create_base
    from sqlalchemy import Column, String

    Storable = create_base()

    class User(Storable):
        pass

    class RegisteredUser(User):
        name = Column(String, nullable=False)
        email = Column(String(200), nullable=False)

    user = session.query(RegisteredUser).filter(User.id == 18).first()

This will automatically create the member ``User._type``, which contains the
name of the table of the concrete class. If we create a ``RegisteredUser``,
the two tables will contain the following values::

    > SELECT * FROM _user;
          _type      | id
    -----------------+----
     user            |  1
     registered_user |  2

    > SELECT * FROM _registered_user;
     id |   name  |     email
    ----+---------+-----------------
      2 | Mrs Bun | nospam@bun.name


If you really want to change the way inheritance is configured, you can do so
using the class member ``__score_db__``:

.. code-block:: python
    :linenos:
    :emphasize-lines: 2-4,7-8

    class User(Storable):
        __score_db__ = {
            'inheritance': 'single-table'
        }

    class RegisteredUser(User):
        name = Column(String)
        email = Column(String(200))

The ``inheritance`` configuration in line 3 will instruct sqlalchemy to create
a single table for all sub-classes. Note that you must not have any columns
with NOT NULL constraints in any child table. Otherwise the database will
raise an error for attempts to create a different type!

This configuration will now create a single table in the database containing
all members::

    > SELECT * FROM _user;
          _type      | id |   name  |     email
    -----------------+----+---------+-----------------
     user            |  1 | NULL    | NULL
     registered_user |  2 | Mrs Bun | nospam@bun.name

It is also possible to configure a class to not support subclassing at all.
This is done by assigning `None` as its inheritance configuration:

.. code-block:: python
    :linenos:
    :emphasize-lines: 3,6

    class User(Storable):
        __score_db__ = {
            'inheritance': None
        }

    class RegisteredUser(User):  # invalid!
        name = Column(String)
        email = Column(String(200))

In this case, the second class declaration will raise an exception in line #6.


.. _db_view:

Automatic VIEWs
---------------

During creation of database tables, this module will also create a view_ for
each class. The aim of the view is to aggregate the members of all parent
classes. These views have the same name as the table, but omit the leading
underscore::

    > SELECT * FROM _registered_user;
     id |   name  |     email
    ----+---------+-----------------
      2 | Mrs Bun | nospam@bun.name

    > SELECT * FROM registered_user;
          _type     | id |   name  |     email
    ----------------+----+---------+-----------------
    registered_user |  2 | Mrs Bun | nospam@bun.name

Note that there is no member called ``_type`` in RegisteredUser, the view just
joins the parent table and allows convenient access to the members as one
would see them in python. The DDL statement is something like the following::

    > CREATE VIEW registered_user AS
    …   SELECT * FROM _user u INNER JOIN _registered_user r ON u.id == r.id;

This statement depends on the :ref:`inheritance configuration
<db_inheritance>`, of course. If we had configured single table inheritance,
it would look different::

    > CREATE VIEW registered_user AS
    …   SELECT * FROM _user WHERE _user._type == 'registered_user';

These views are strictly for humans. The ORM layer (provided by sqlalchemy_)
is, of course, smart enough to make as few joins as possible during queries.
This shouldn't come as a surprise, as the external library doesn't have a clue
about these views.


.. _db_config_member:

Fine-Grained Configuration
--------------------------

We have already seen that inheritance can be configured via a special class
member called ``__score_db__``. There are a few more available options while
configuring the class:

- ``inheritance``: Determines how :ref:`inheritance <db_inheritance>` should
  be configured. Valid values are:

  - ``joined-table`` - creates a table for each sub-class and joins them
    whenever necessary. This is the default.
  - ``single-table`` - creates a single table containing all members of all
    sub-classes.
  - `None` - the class does not support sub-classing.

- ``type_column``: Name of the column to use to determine the class's actual
  type. The column will be created automatically if it does not already exist.
  Defaults to ``_type``.

- ``type_name``: How this class should be called in the ``type_column``.
  Defaults to this class's :ref:`view <db_view>` name.

- ``parent``: The parent class of this class in the inheritance chain toward
  the :ref:`base class <db_base_class>`. Note that classes deriving from the base
  class directly will have `None`. This will be determined automatically.

- ``base``: Reference to the :ref:`base class <db_base_class>`.

Note that there are very few cases where one might want to set any of these
values. The safest to configure manually, and the one where deviating from the
default makes any sense at all, is the ``inheritance`` configuration.

The base class will make sure that all these values are actually present in
this class nonetheless:

.. code-block:: python
    :linenos:

    class User(Storable):
        pass

    assert User.__score_db__['inheritance'] == 'joined-table'
    assert User.__score_db__['type_column'] == '_type'
    assert User.__score_db__['type_name'] == 'user'
    assert User.__score_db__['parent'] == None
    assert User.__score_db__['base'] is Storable


.. _db_data_loading:

Data Loading
------------

When starting a new project, it is quite convenient to have some test data in
the database. `score.db` addresses this need by providing a data loader, that
is capable of reading yaml_ files. You can have a look at the
:download:`example file <../../tutorial/moswblog.yaml>` used during the
:ref:`tutorial <tutorial>`.

The format of the file is very simple:
- define a section for each class::

    moswblog.db.user.InternalUser:

- add "objects" to this section, giving each one a unique name::

    moswblog.db.user.InternalUser:
        JohnCleese:

- add "members" to each object to your liking::

    moswblog.db.user.InternalUser:
        JohnCleese:
            name: John Cleese

- since relationships are already configured via SQLAlchemy, you can reference
  other objects using the unique name you gave earlier::

    moswblog.db.content.Blog:
        News:
            name: News-Blog!
            owner: JohnCleese

That's it! You can load the data using :func:`.load_data`.

.. _yaml: http://www.yaml.org/


.. _db_session_extensions:

Session Extensions
------------------

We have compiled a few common patterns during day to day usage of an ORM and
implemented them in the form of a mixin, which will be automatically added to
SQLAlchemy's session class.

.. autoclass:: score.db.SessionMixin

    .. automethod:: score.db.SessionMixin.mktmp

    .. automethod:: score.db.SessionMixin.by_ids


.. _db_enumerations:

Enumerations
------------

This module also provides a convenient Enum class, which can be used to
interface enumerations in the database. It sub-classes python's built-in
:class:`enum.Enum` type and adds a function to extract an appropriate
SQLAlchemy type:

.. code-block:: python

    from .base import Base
    from score.db import Enum
    from sqlalchemy import Column

    class Status(Enum):
        ONLINE = 'online'
        OFFLINE = 'offline'

    class Article(Base):
        status = Column(Status.db_type(), nullable=False)

    Article(status=Status.ONLINE)


Relationship Helpers
--------------------

A common need during initial application development is the implementation of
relationships. Although SQLAlchemy provides various features to support this,
it provides no ready-to-use class or function for implementing m:n
relationships, for example. That's why we provide our own:

.. code-block:: python

    class User(Storable):
        name = Column(String, nullable=False)

    class Group(Storable):
        name = Column(String, nullable=False)

    UserGroup = create_relationship_class(
        User, Group, 'groups', sorted=False, duplicates=False, backref='users')

    user = User('Mousebender')
    group = Group('Customer')
    user.groups.append(group)
    session.flush()
    # the database now contains an entry in the intermidiate table
    # _user_group linking the objects.


API
===

Configuration
-------------

.. autofunction:: score.db.init

.. autoclass:: score.db.ConfiguredDbModule

    .. attribute:: Base

        The configured :ref:`base class <db_base_class>`. Can be `None` if no base
        class was configured.

    .. attribute:: destroyable

        Whether destructive operations may be performed on the database. This
        value will be consulted before any such operations are performed.
        Application developers are also advised to make use of this value
        appropriately.

    .. attribute:: engine

        An SQLAlchemy :class:`Engine <sqlalchemy.engine.Engine>`.

    .. attribute:: Session

        An SQLAlchemy :class:`Session <sqlalchemy.orm.session.Session>` class.
        Can be instanciated without arguments:

        >>> session = dbconf.Session()
        >>> session.execute('SELECT 1 FROM DUAL')

    .. automethod:: score.db.ConfiguredDbModule.create

    .. automethod:: score.db.ConfiguredDbModule.destroy

Helper Functions
----------------

.. autofunction:: score.db.engine_from_config

.. autofunction:: score.db.cls2tbl

.. autofunction:: score.db.tbl2cls

.. autofunction:: score.db.create_base

Postgresql-Specific
```````````````````

.. autofunction:: score.db.pg.destroy

.. autofunction:: score.db.pg.list_sequences

.. autofunction:: score.db.pg.list_tables

.. autofunction:: score.db.pg.list_views

SQLite-Specific
```````````````

.. autofunction:: score.db.sqlite.destroy

.. autofunction:: score.db.sqlite.list_tables

.. autofunction:: score.db.sqlite.list_triggers

.. autofunction:: score.db.sqlite.list_views

Data Loading
------------

.. autofunction:: score.db.load_data

Relationships
-------------

.. autofunction:: score.db.helpers.create_relationship_class

.. autofunction:: score.db.helpers.create_collection_class

.. _view: https://en.wikipedia.org/wiki/View_%28SQL%29
.. _SQLAlchemy: http://docs.sqlalchemy.org/en/latest/
.. _ORM: http://en.wikipedia.org/wiki/Object-relational_mapping
