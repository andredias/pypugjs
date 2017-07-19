from __future__ import absolute_import  # noqa
from .parser import Parser  # noqa
from .compiler import Compiler  # noqa
from .utils import process  # noqa
from .filters import register_filter  # noqa
from .ext import html  # noqa


def simple_convert(t):
    return html.process_pugjs(t)
