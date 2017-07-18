from __future__ import absolute_import
from .parser import Parser
from .compiler import Compiler
from .utils import process
from .filters import register_filter
from .ext import html


def simple_convert(t):
    return html.process_pugjs(t)

