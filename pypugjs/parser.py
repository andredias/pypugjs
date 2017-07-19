from __future__ import absolute_import
from .lexer import Lexer
from . import nodes
import six


class Parser(object):
    def __init__(self, str, filename=None, **options):
        self.input = str
        self.lexer = Lexer(str, **options)
        self.filename = filename
        self.bloks = {}
        self.options = options
        self.contexts = [self]
        self.extending = False
        self._spaces = None

    def context(self, parser):
        if parser:
            self.context.append(parser)
        else:
            self.contexts.pop()

    def advance(self):
        return self.lexer.advance()

    def skip(self, n):
        while n > 1:  # > 0?
            self.advance()
            n -= 1

    def peek(self):
        p = self.lookahead(1)
        return p

    def line(self):
        return self.lexer.lineno

    def lookahead(self, n):
        return self.lexer.lookahead(n)

    def parse(self):
        block = nodes.Block()
        parser = None
        block.line = self.line()

        while 'eos' != self.peek().type:
            if 'newline' == self.peek().type:
                self.advance()
            else:
                block.append(self.parse_expr())

        parser = self.extending
        if parser:
            self.context(parser)
            ast = parser.parse()
            self.context()
            return ast

        return block

    def expect(self, type):
        t = self.peek().type
        if t == type:
            return self.advance()
        else:
            raise Exception('expected "%s" but got "%s" in file %s on line %d' %
                            (type, t, self.filename, self.line()))

    def accept(self, type):
        if self.peek().type == type:
            return self.advance()

    def parse_expr(self):
        t = self.peek().type
        if 'yield' == t:
            self.advance()
            block = nodes.Block()
            block._yield = True
            return block
        elif t in ('id', 'class'):
            tok = self.advance()
            new_div = self.lexer.tok('tag', 'div')
            new_div.inline_level = tok.inline_level
            self.lexer.stash.append(new_div)
            self.lexer.stash.append(tok)
            return self.parse_expr()

        func_name = 'parse_%s' % t.lower()
        if hasattr(self, func_name):
            return getattr(self, func_name)()
        else:
            raise Exception('unexpected token "%s" in file %s on line %d' %
                            (t, self.filename, self.line()))

    def parse_string(self):
        tok = self.expect('string')
        node = nodes.String(tok.val, inline=tok.inline_level > 0)
        node.line = self.line()
        return node

    def parse_text(self):
        tok = self.expect('text')
        node = nodes.Text(tok.val)
        node.line = self.line()
        return node

    def parse_block_expansion(self):
        if ':' == self.peek().type:
            self.advance()
            return nodes.Block(self.parse_expr())
        else:
            return self.block()

    def parse_assignment(self):
        tok = self.expect('assignment')
        return nodes.Assignment(tok.name, tok.val)

    def parse_code(self):
        tok = self.expect('code')
        node = nodes.Code(tok.val, tok.buffer, tok.escape)  # tok.escape
        block, i = None, 1
        node.line = self.line()
        while self.lookahead(i) and 'newline' == self.lookahead(i).type:
            i += 1
        block = 'indent' == self.lookahead(i).type
        if block:
            self.skip(i - 1)
            node.block = self.block()
        return node

    def parse_comment(self):
        tok = self.expect('comment')

        if 'indent' == self.peek().type:
            node = nodes.BlockComment(tok.val, self.block(), tok.buffer)
        else:
            node = nodes.Comment(tok.val, tok.buffer)

        node.line = self.line()
        return node

    def parse_doctype(self):
        tok = self.expect('doctype')
        node = nodes.Doctype(tok.val)
        node.line = self.line()
        return node

    def parse_filter(self):
        tok = self.expect('filter')
        attrs = self.accept('attrs')
        self.lexer.pipeless = True
        block = self.parse_text_block()
        self.lexer.pipeless = False

        node = nodes.Filter(tok.val, block, attrs and attrs.attrs)
        node.line = self.line()
        return node

    def parse_a_s_t_filter(self):
        tok = self.expect('tag')
        attrs = self.accept('attrs')

        self.expect(':')
        block = self.block()

        node = nodes.Filter(tok.val, block, attrs and attrs.attrs)
        node.line = self.line()
        return node

    def parse_each(self):
        tok = self.expect('each')
        node = nodes.Each(tok.code, tok.keys)
        node.line = self.line()
        node.block = self.block()
        return node

    def parse_conditional(self):
        tok = self.expect('conditional')
        node = nodes.Conditional(tok.val, tok.sentence)
        node.line = self.line()
        node.block = self.block()
        while True:
            t = self.peek()
            if 'conditional' == t.type and node.can_append(t.val):
                node.append(self.parse_conditional())
            else:
                break
        return node

    def parse_extends(self):
        path = self.expect('extends').val.strip('"\'')
        return nodes.Extends(path)

    def parse_call(self):
        tok = self.expect('call')
        name = tok.val
        args = tok.args
        if args is None:
            args = ""
        block = self.block() if 'indent' == self.peek().type else None
        return nodes.Mixin(name, args, block, True)

    def parse_mixin(self):
        tok = self.expect('mixin')
        name = tok.val
        args = tok.args
        if args is None:
            args = ""
        block = self.block() if 'indent' == self.peek().type else None
        return nodes.Mixin(name, args, block, block is None)

    def parse_block(self):
        block = self.expect('block')
        mode = block.mode
        name = block.val.strip()
        block = self.block(cls=nodes.CodeBlock) if 'indent' == self.peek().type else nodes.CodeBlock(nodes.Literal(''))
        block.mode = mode
        block.name = name
        return block

    def parse_include(self):
        path = self.expect('include').val.strip()
        return nodes.Include(path)

    def parse_text_block(self, tag=None):
        text = nodes.Text()
        text.line = self.line()
        if (tag):
            text.parent == tag
        spaces = self.expect('indent').val
        if not self._spaces:
            self._spaces = spaces
        indent = ' ' * (spaces - self._spaces)
        while 'outdent' != self.peek().type:
            t = self.peek().type
            if 'newline' == t:
                text.append('\n')
                self.advance()
            elif 'indent' == t:
                text.append('\n')
                for node in self.parse_text_block().nodes:
                    text.append(node)
                text.append('\n')
            else:
                text.append(indent + self.advance().val)

        if spaces == self._spaces:
            self._spaces = None
        self.expect('outdent')
        return text

    def block(self, cls=nodes.Block):
        block = cls()
        block.line = self.line()
        self.expect('indent')
        while 'outdent' != self.peek().type:
            if 'newline' == self.peek().type:
                self.advance()
            else:
                block.append(self.parse_expr())
        self.expect('outdent')
        return block

    def process_inline(self, current_tag, current_level):
        next_level = current_level + 1
        while self.peek().inline_level == next_level:
            current_tag.block.append(self.parse_expr())

        if self.peek().inline_level > next_level:
            self.process_inline(current_tag, next_level)

    def process_tag_text(self, tag):
        if self.peek().inline_level < tag.inline_level:
            return

        if not self.lookahead(2).inline_level > tag.inline_level:
            tag.text = self.parse_text()
            return

        while self.peek().inline_level == tag.inline_level and self.peek().type == 'string':
            tag.block.append(self.parse_expr())

            if self.peek().inline_level > tag.inline_level:
                self.process_inline(tag, tag.inline_level)

    def parse_tag(self):
        i = 2
        if 'attrs' == self.lookahead(i).type:
            i += 1

        if ':' == self.lookahead(i).type:
            if 'indent' == self.lookahead(i + 1).type:
                raise Exception('unexpected token "indent" in file %s on line %d' %
                                (self.filename, self.line()))

        tok = self.advance()
        tag = nodes.Tag(tok.val, buffer=tok.val[0] == '#')
        tag.inline_level = tok.inline_level
        dot = None

        tag.line = self.line()

        while True:
            t = self.peek().type
            if t in ('id', 'class'):
                tok = self.advance()
                tag.set_attribute(tok.type, '"%s"' % tok.val, True)
                continue
            elif 'attrs' == t:
                tok = self.advance()
                for n, v in six.iteritems(tok.attrs):
                    tag.set_attribute(n, v, n in tok.static_attrs)
                continue
            else:
                break

        v = self.peek().val
        if '.' == v:
            dot = tag.text_only = True
            self.advance()
        elif '<' == v:  # For inline elements
            tag.inline = True
            self.advance()

        t = self.peek().type
        if 'code' == t:
            tag.code = self.parse_code()
        elif ':' == t:
            self.advance()
            tag.block = nodes.Block()
            tag.block.append(self.parse_expr())
        elif 'string' == t:
            self.process_tag_text(tag)
        elif 'text' == t:
            tag.text = self.parse_text()

        while 'newline' == self.peek().type:
            self.advance()

        if 'indent' == self.peek().type:
            if tag.text_only:
                self.lexer.pipeless = True
                tag.block = self.parse_text_block(tag)
                self.lexer.pipeless = False
            else:
                block = self.block()
                if tag.block:
                    for node in block.nodes:
                        tag.block.append(node)
                else:
                    tag.block = block

        return tag
