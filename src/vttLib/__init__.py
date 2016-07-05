from __future__ import print_function, division, absolute_import
import re
import string
import array
from collections import deque

from pyparsing import (
    Word, nums, Suppress, pyparsing_common, oneOf, tokenMap, Combine,
    OneOrMore, Optional, Literal, nestedExpr, Group, cStyleComment,
    ParseException
)

from fontTools.ttLib import newTable, TTLibError
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.misc.py23 import StringIO


class VTTLibError(TTLibError):
    pass


VTT_MNEMONIC_FLAGS = {
    # Direction
    "X": '1',    # X axis
    "Y": '0',    # Y axis

    # Outline
    "O": '1',    # Use original outline
    "N": '0',    # Use gridfitted outline

    # Rounding or Line Relation
    "R": '1',    # Round distance; or perpedicular to line
    "r": '0',    # Do not round distance; or parallel to line

    # Reference Point Autoset
    "M": '1',    # Set rp0 to point number on the stack
    "m": '0',    # Do not set rp0

    # Reference Point Usage
    "1": '1',    # Use rp1
    "2": '0',    # Use rp2

    # Minimum Distance flag
    ">": '1',    # Obey minimum distance
    "<": '0',    # Do not obey minimum distance

    # Color (Distance Type)
    "Gr": '00',  # Gray
    "Bl": '01',  # Black
    "Wh": '10',  # White
}


alpha_upper = string.ascii_uppercase

mnemonic = Word(
    alpha_upper, bodyChars=alpha_upper + nums
).setResultsName("mnemonic")

stack_item = Suppress(",") + (pyparsing_common.signedInteger | Suppress("*"))

flag = oneOf(list(VTT_MNEMONIC_FLAGS.keys()))
# convert flag to binary string
flag.setParseAction(tokenMap(lambda t: VTT_MNEMONIC_FLAGS[t]))
flags = Combine(OneOrMore(flag)).setResultsName("flags")

delta_point_index = pyparsing_common.integer.setResultsName("point_index")
delta_rel_ppem = pyparsing_common.integer.setResultsName("rel_ppem")
delta_step_no = pyparsing_common.signedInteger.setResultsName("step_no")
# the step denominator is only used in VTT's DELTA[CP]* instructions,
# and must always be 8 (sic!), so we can suppress it.
delta_spec = (delta_point_index + Suppress("@") + delta_rel_ppem +
              delta_step_no + Optional(Literal("/8")).suppress())

delta = nestedExpr("(", ")", delta_spec, ignoreExpr=None)

deltas = Group(OneOrMore(delta)).setResultsName("deltas")

args = deltas | flags

stack_items = OneOrMore(stack_item).setResultsName("stack_items")

instruction = Group(
    mnemonic + Suppress("[") + Optional(args) + Suppress("]") +
    Optional(stack_items)
)

pragma_memonic = Word("#", bodyChars=alpha_upper).setResultsName("mnemonic")

pragma = Group(pragma_memonic + Optional(stack_items))

comment = cStyleComment.suppress()

vtt_assembly = OneOrMore(comment | pragma | instruction)


def set_cvt_table(font, data):
    data = re.sub(r"/\*.*?\*/", "", data, flags=re.DOTALL)
    values = array.array("h")
    # control values are defined in VTT Control Program as colon-separated
    # INDEX: VALUE pairs
    for m in re.finditer(r"^\s*([0-9]+):\s*(-?[0-9]+)", data, re.MULTILINE):
        index, value = int(m.group(1)), int(m.group(2))
        for i in range(1 + index - len(values)):
            # missing CV indexes default to zero
            values.append(0)
        values[index] = value
    if len(values):
        if "cvt " not in font:
            font["cvt "] = newTable("cvt ")
        font["cvt "].values = values


class VTTProgram(Program):

    def fromAssembly(self, string):
        tokens = vtt_assembly.parseString(string, parseAll=True)

        push_on = True
        push_indexes = [0]
        stream = [deque()]
        pos = 1
        for t in tokens:
            mnemonic = t.mnemonic

            if mnemonic in ("USEMYMETRICS", "OVERLAP", "OFFSET"):
                # XXX these are not part of the TT instruction set...
                continue

            elif mnemonic == "#PUSHON":
                push_on = True
                continue
            elif mnemonic == "#PUSHOFF":
                push_on = False
                continue

            elif mnemonic == "#BEGIN":
                # XXX shouldn't these be ignored in #PUSHOFF mode?
                push_indexes.append(pos)
                stream.append(deque())
                pos += 1
                continue
            elif mnemonic == "#END":
                pi = push_indexes.pop()
                stack = stream[pi]
                if len(stack):
                    stream[pi] = "PUSH[] %s" % " ".join([str(i) for i in stack])
                continue

            elif mnemonic == "#PUSH":
                # XXX push stack items whether or not in #PUSHON/OFF?
                stream.append(
                    "PUSH[] %s" % " ".join([str(i) for i in t.stack_items]))
                pos += 1
                continue

            elif mnemonic.startswith(("DLTC", "DLTP", "DELTAP", "DELTAC")):
                assert push_on
                n = len(t.deltas)
                assert n > 0
                stack = stream[push_indexes[-1]]
                stack.appendleft(n)
                for point_index, rel_ppem, step_no in reversed(t.deltas):
                    if mnemonic.startswith(("DELTAP", "DELTAC")):
                        rel_ppem -= 9  # subtract the default 'delta base'
                    stack.appendleft(point_index)
                    # -8: 0, ... -1: 7, 1: 8, ... 8: 15
                    selector = (step_no + 7) if step_no > 0 else (step_no + 8)
                    stack.appendleft((rel_ppem << 4) | selector)
                if mnemonic.startswith("DLT"):
                    mnemonic = mnemonic.replace("DLT", "DELTA")
            else:
                if push_on:
                    for i in reversed(t.stack_items):
                        stream[push_indexes[-1]].appendleft(i)
                else:
                    assert not t.stack_items

            stream.append("%s[%s]" % (mnemonic, t.flags))
            pos += 1

        assert len(push_indexes) == 1 and push_indexes[0] == 0, push_indexes
        stack = stream[0]
        if len(stack):
            stream[0] = "PUSH[] %s" % " ".join([str(i) for i in stack])

        stream = [i for i in stream if i]

        super(VTTProgram, self).fromAssembly(stream)


def pformat_tti(program, preserve=False):
    from fontTools.ttLib.tables.ttProgram import _pushCountPat

    assembly = program.getAssembly(preserve=preserve)
    stream = StringIO()
    i = 0
    nInstr = len(assembly)
    while i < nInstr:
        instr = assembly[i]
        stream.write(instr)
        stream.write("\n")
        m = _pushCountPat.match(instr)
        i = i + 1
        if m:
            nValues = int(m.group(1))
            line = []
            j = 0
            for j in range(nValues):
                if j and not (j % 25):
                    stream.write(' '.join(line))
                    stream.write("\n")
                    line = []
                line.append(assembly[i+j])
            stream.write(' '.join(line))
            stream.write("\n")
            i = i + j + 1
    return stream.getvalue()


def transform_assembly(data, name):
    program = VTTProgram()
    try:
        program.fromAssembly(data)
    except ParseException as e:
        import sys
        sys.stderr.write(name + "\n\n")
        sys.stderr.write(data + "\n\n")
        raise VTTLibError(e)
    # need to compile bytecode for PUSH optimization
    program.getBytecode()
    return program


def get_vtt_assembly(font, name):
    if "TSI1" not in font:
        raise VTTLibError("The font contains no 'TSI1' table")
    tsi1 = font['TSI1']

    try:
        if name in ("cvt", "ppgm", "prep", "fpgm"):
            if name == "prep":
                name = "ppgm"
            data = tsi1.extraPrograms[name]
        else:
            data = tsi1.glyphPrograms[name]
    except KeyError:
        raise VTTLibError("Can't find '%s' in TSI1 table" % name)

    # normalize line endings as VTT somehow uses Macintosh-style CR...
    return "\n".join(data.splitlines())


def compile_instructions(font, ship=True):
    control_program = get_vtt_assembly(font, 'cvt')
    set_cvt_table(font, control_program)

    for tag in ("prep", "fpgm"):
        if tag not in font:
            font[tag] = newTable(tag)
        data = get_vtt_assembly(font, tag)
        program = transform_assembly(data, tag)
        if not program:
            raise VTTLibError("%s program is empty" % tag)
        font[tag].program = program

    if 'glyf' not in font:
        raise VTTLibError("Missing 'glyf' table; not a TrueType font")
    glyf_table = font['glyf']
    for glyph_name in font.getGlyphOrder():
        try:
            data = get_vtt_assembly(font, glyph_name)
        except VTTLibError:
            continue
        program = transform_assembly(data, glyph_name)
        if program:
            glyph = glyf_table[glyph_name]
            glyph.program = program

    if ship:
        for tag in ("TSI%d" % i for i in (0, 1, 2, 3, 5)):
            if tag in font:
                del font[tag]
