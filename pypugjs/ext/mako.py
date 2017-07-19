from pypugjs import Compiler as _Compiler
from pypugjs.runtime import attrs as _attrs
from pypugjs.utils import process
ATTRS_FUNC = '__pypugjs_attrs'
ITER_FUNC = '__pypugjs_iter'


def attrs(attrs, terse=False):
    return _attrs(attrs, terse, MakoUndefined)


class Compiler(_Compiler):
    use_runtime = True

    def compile_top(self):
        return '# -*- coding: utf-8 -*-\n<%%! from pypugjs.runtime import attrs as %s, iteration as %s\nfrom mako.runtime import Undefined %%>' % (
            ATTRS_FUNC, ITER_FUNC)

    def interpolate(self, text, escape=True):
        return self._interpolate(text, lambda x: '${%s}' % x)

    def visit_codeblock(self, block):
        if self.mixing > 0:
            self.buffer('${caller.body() if caller else ""}')
        else:
            self.buffer('<%%block name="%s">' % block.name)
            if block.mode == 'append':
                self.buffer('${parent.%s()}' % block.name)
            self.visit_block(block)
            if block.mode == 'prepend':
                self.buffer('${parent.%s()}' % block.name)
            self.buffer('</%block>')

    def visit_mixin(self, mixin):
        self.mixing += 1
        if not mixin.call:
            self.buffer('<%%def name="%s(%s)">' % (mixin.name, mixin.args))
            self.visit_block(mixin.block)
            self.buffer('</%def>')
        elif mixin.block:
            self.buffer('<%%call expr="%s(%s)">' % (mixin.name, mixin.args))
            self.visit_block(mixin.block)
            self.buffer('</%call>')
        else:
            self.buffer('${%s(%s)}' % (mixin.name, mixin.args))
        self.mixing -= 1

    def visit_assignment(self, assignment):
        self.buffer('<%% %s = %s %%>' % (assignment.name, assignment.val))

    def visit_extends(self, node):
        path = self.format_path(node.path)
        self.buffer('<%%inherit file="%s"/>' % (path))

    def visit_include(self, node):
        path = self.format_path(node.path)
        self.buffer('<%%include file="%s"/>' % (path))
        self.buffer('<%%namespace file="%s" import="*"/>' % (path))

    def visit_conditional(self, conditional):
        type_code = {
            'if': lambda x: 'if %s' % x,
            'unless': lambda x: 'if not %s' % x,
            'elif': lambda x: 'elif %s' % x,
            'else': lambda x: 'else'
        }
        self.buf.append('\\\n%% %s:\n' % type_code[conditional.type](conditional.sentence))
        if conditional.block:
            self.visit(conditional.block)
            for next in conditional.next:
                self.visit_conditional(next)
        if conditional.type in ['if', 'unless']:
            self.buf.append('\\\n% endif\n')

    def visit_var(self, var, escape=False):
        return '${%s%s}' % (var, '| h' if escape else '| n')

    def visit_code(self, code):
        if code.buffer:
            val = code.val.lstrip()
            val = self.var_processor(val)
            self.buf.append(self.visit_var(val, code.escape))
        else:
            self.buf.append('<%% %s %%>' % code.val)

        if code.block:
            # if not code.buffer: self.buf.append('{')
            self.visit(code.block)
            # if not code.buffer: self.buf.append('}')

            if not code.buffer:
                code_tag = code.val.strip().split(' ', 1)[0]
                if code_tag in self.autoclose_code:
                    self.buf.append('</%%%s>' % code_tag)

    def visit_each(self, each):
        self.buf.append('\\\n%% for %s in %s(%s,%d):\n' % (','.join(each.keys), ITER_FUNC, each.obj, len(each.keys)))
        self.visit(each.block)
        self.buf.append('\\\n% endfor\n')

    def attributes(self, attrs):
        return "${%s(%s, undefined=Undefined) | n}" % (ATTRS_FUNC, attrs)


def preprocessor(source):
    return process(source, compiler=Compiler)
