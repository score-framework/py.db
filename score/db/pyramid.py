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
This package :ref:`integrates <framework_integration>` the module with
pyramid_.

.. _pyramid: http://docs.pylonsproject.org/projects/pyramid/en/latest/
"""


def init(confdict, configurator, ctx_conf=None):
    """
    Apart from calling the :func:`base initializer <score.db.init>`, this
    function will also register a :ref:`reified request method
    <pyramid:adding_request_method>` called ``db`` on all :ref:`Request
    <pyramid:request_module>` objects that provides a session with the same
    lifetime as the request. Example use:

    >>> request.db.query(User).first()
    """
    import score.db
    db_conf = score.db.init(confdict, ctx_conf)
    if not ctx_conf:
        def db(request):
            session = db_conf.Session()
            def cleanup(request):
                session.close()
            request.add_finished_callback(cleanup)
            return session
        configurator.add_request_method(db, reify=True)
    return db_conf


def create_context_factory(cls, member='id', matchkey=None, match_convert=None):
    """
    Creates a :term:`context <pyramid:context>` generating function.
    The function will look for the specified member in the :term:`request
    <pyramid:request>`'s :ref:`matchdict <pyramid:matchdict>`.

    By default, this will create a function that matches the id in a URL, and
    thus allows you to use it somewhat like this:

    >>> config.add_route('article', '/article/{id}',
                         factory=create_context_factory(db.Article))

    It is possible to define a different *member* to use:

    >>> config.add_route('article', '/article/{slug}',
                         factory=create_context_factory(db.Article, 'slug'))

    The function will by default look for a key with the same name as the
    member in the matchdict, but it is possible to provide a different
    *matchkey*:

    >>> config.add_route('article', '/article/{title}',
                         factory=create_context_factory(db.Article, 'slug', 'title'))

    The function will further try to find the correct conversion function, for
    converting the string in the matchdict to the correct type (for example, it
    will convert ``id`` values to integers), but the conversion function can
    be specified explicitly as *match_convert*:

    >>> def match_convert(request, match):
    ...     return datetime(match)
    ...
    >>> config.add_route('article', '/article/{datetime}',
                         factory=create_context_factory(db.Article, 'datetime',
                                                 match_convert=datetime),
    """
    if matchkey is None:
        matchkey = member
    def context_constructor(request):
        match = request.matchdict[matchkey]
        if match_convert is None and member == 'id':
            match = int(match)
        elif match_convert is not None:
            match = match_convert(request, match)
        return request.db.query(cls).\
            filter(getattr(cls, member) == match).\
            first()
    return context_constructor


def create_default_pregenerator(cls, member='id', matchkey=None,
                                member_convert=None):
    """
    Creates a simple :term:`pregenerator <pyramid:pregenerator>` that can be
    used in combination with :func:`.create_context_factory`:

    >>> config.add_route('article', '/article/{id}',
    ...                  factory=create_context_factory(db.Article),
    ...                  pregenerator=create_default_pregenerator(db.Article)
    ...
    >>> request.route_url('article', article_obj)
    /article/51

    All parameters are analogous to those of :func:`.create_context_factory`.
    """
    if matchkey is None:
        matchkey = member
    def pregenerator(request, elements, kw):
        if not elements:
            return elements, kw
        obj = elements[0]
        if not isinstance(obj, cls):
            return elements, kw
        memberval = getattr(obj, member)
        if member_convert is not None:
            memberval = member_convert(request, memberval)
        kw[matchkey] = memberval
        elements = tuple(v for k, v in enumerate(elements) if k > 0)
        return elements, kw
    return pregenerator


class AutologinAuthenticationPolicy:
    """
    An :term:`authentication policy <pyramid:authentication policy>` that will
    automatically check if a *username* and *password* were submitted and log
    the user in if the credentials match.

    The constructor expects another authentication *backend* (i.e. another
    authentication policy), that will do the actual work, and a *userclass*
    that has the members *username* and *password*. The class is assuming that
    the password member is an
    :class:`sqlalchemy_utils.types.password.PasswordType` and will thus compare
    the POSTed *password* directly.

    Example user class:

    .. code-block:: python

        from sqlalchemy import (
            Column,
            String,
        )
        from sqlalchemy_utils.types.password import PasswordType

        class User(Base):
            username = Column(Integer)
            password = Column(PasswordType(schemes=['pbkdf2_sha512']))
            groups = ('group:knight', 'group:philosopher')

    Example setup:

    .. code-block:: python

        authbase = AuthTktAuthenticationPolicy('spambaconeggsandspam',
                callback=lambda user_id, req: req.user.groups, hashalg='sha512')
        auth = AutologinAuthenticationPolicy(authbase, db.User)
        config.set_authentication_policy(auth)
        config.add_request_method(auth.user, 'user', property=True)

    And the form to trigger the automatic login on any URL:

    .. code-block:: jinja

        <form method="post">
            <input name="username" />
            <input name="password" type="password" />
            <input type="submit" />
        </form>
    """

    def __init__(self, backend, userclass):
        self.backend = backend
        self.usercls = userclass

    def remember(self, request, user, **kw):
        request._user = user
        return self.backend.remember(request, user.id, **kw)

    def unauthenticated_userid(self, request):
        return self.backend.unauthenticated_userid(request)

    def effective_principals(self, request):
        return self.backend.effective_principals(request)

    def forget(self, request):
        if hasattr(request, '_user'):
            del request._user
        return self.backend.forget(request)

    def user(self, request):
        """
        The user object that is logged in in provided *request*.
        """
        self.authenticated_userid(request)
        return request._user

    def authenticated_userid(self, request):
        if self._dologin(request):
            return request._user
        userid = self.unauthenticated_userid(request)
        if not userid:
            request._user = None
            return
        request._user = request.db.query(self.usercls).\
            filter(self.usercls.id == userid).\
            first()
        return request._user

    def _dologin(self, request):
        if hasattr(request, '_user'):
            return True
        if 'username' not in request.POST or 'password' not in request.POST:
            return False
        request._user = None
        user = request.db.query(self.usercls).\
            filter(self.usercls.username == request.POST['username']).\
            first()
        if not user:
            return False
        if user.password == request.POST['password']:
            request._user = user
        if not request._user:
            return False
        request.add_response_callback(self._login_callback(request))
        return True

    def _login_callback(self, request):
        headers = self.remember(request, request._user)
        def callback(request, response):
            for header in headers:
                response.headerlist.append(header)
        return callback
