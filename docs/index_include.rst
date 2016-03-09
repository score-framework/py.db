.. module:: score.db
.. role:: faint
.. role:: confkey

********
score.db
********

Introduction
============

This module provides functions and classes that implement our database
standards and provides helper functions for automating various operations.
We are using SQLAlchemy_ as our database connectivity and ORM_ layer.

.. _db_base:

Base Class
----------

Database classes should derive from a base class constructed by a call to
:func:`score.db.create_base`. The class will automatically determine a table
name and automatically establish an ``id`` and a ``_type`` column. The
ollowing class will be assigned the table name ``_user`` (as returned by
:func:`.cls2tbl`) and its id column as primary key:

.. code-block:: python
    :linenos:

    from score.db import create_base

    Storable = create_base()

    class User(Storable):
        pass


.. _db_data_loading:

Data Loading
============

When starting a new project, it is quite convenient to have some test data in
the database. `score.db` addresses this need by providing a data loader, that
is capable of reading yaml_ files. You can have a look at the
:download:`example file <../../tutorial/moswblog.yaml>` used during the
:ref:`blog tutorial <blog_tutorial>`.

The format of the file is very simple:
- define a section for each class::

    moswblog.db.user.InternalUser:

- add "objects" to this section, giving each one a unique name::

    moswblog.db.user.InternalUser:
        JohnCleese:

- add "members" to each object to your liking::

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
==================

We have compiled a few common patterns during day to day usage of an ORM and
implemented them in the form of a mixin, which will be automatically added to
SQLAlchemy's session class.

.. autoclass:: score.db.SessionMixin

    .. automethod:: score.db.SessionMixin.mktmp

    .. automethod:: score.db.SessionMixin.by_ids

.. _db_enumerations:

Enumerations
============

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
====================

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


More Details!
=============

The default configuration is intended to give a quick-start into the
framework. If you know SQLAlchemy_ and/or want to have more control on the
details of table creation or inheritance mapping, have a look at the page
describing this module's :ref:`inner workings <db_internals>`.

.. _SQLAlchemy: http://docs.sqlalchemy.org/en/latest/
.. _ORM: http://en.wikipedia.org/wiki/Object-relational_mapping


Configuration
=============

.. autofunction:: score.db.init

.. autoclass:: score.db.ConfiguredDbModule

    .. attribute:: Base

        The configured :ref:`base class <db_base>`. Can be `None` if no base
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
================

.. autofunction:: score.db.engine_from_config

.. autofunction:: score.db.cls2tbl

.. autofunction:: score.db.tbl2cls

.. autofunction:: score.db.create_base

Postgresql-Specific
-------------------

.. autofunction:: score.db.pg.destroy

.. autofunction:: score.db.pg.list_sequences

.. autofunction:: score.db.pg.list_tables

.. autofunction:: score.db.pg.list_views

SQLite-Specific
---------------

.. autofunction:: score.db.sqlite.destroy

.. autofunction:: score.db.sqlite.list_tables

.. autofunction:: score.db.sqlite.list_triggers

.. autofunction:: score.db.sqlite.list_views

Data Loading
============

.. autofunction:: score.db.load_data

Relationship API
================

.. autofunction:: score.db.helpers.create_relationship_class

.. autofunction:: score.db.helpers.create_collection_class

.. toctree::
    :hidden:

    internals

