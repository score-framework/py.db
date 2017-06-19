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

from ._init import init, ConfiguredDbModule, engine_from_config
from ._conf import create_base
from .helpers import (IdType, JSON as JsonType, cls2tbl, tbl2cls,
                      create_collection_class, create_relationship_class)

from .dataloader import load_yaml, load_url, load_data, DataLoaderException
from .dbenum import Enum
from .alembic import _import_dummy
from ._session import SessionMixin
from ._sa_stmt import (generate_create_inheritance_view_statement,
                       generate_drop_inheritance_view_statement)

__version__ = '0.5.12'

# avoid "unused variable" warnings from IDEs
_import_dummy

__all__ = (
    'init', 'ConfiguredDbModule', 'engine_from_config', 'create_base', 'IdType',
    'JsonType', 'cls2tbl', 'tbl2cls', 'create_collection_class',
    'create_relationship_class', 'load_yaml', 'load_url', 'load_data',
    'DataLoaderException', 'Enum', 'SessionMixin',
    'generate_create_inheritance_view_statement',
    'generate_drop_inheritance_view_statement')
