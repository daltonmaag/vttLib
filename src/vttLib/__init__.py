from __future__ import (
    print_function, division, absolute_import, unicode_literals)
import re
import array
from collections import deque, namedtuple, OrderedDict

from .parser import AssemblyParser, ParseException

from fontTools.ttLib import newTable, TTLibError
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.misc.py23 import StringIO, tobytes, tounicode, tostr
from fontTools.ttLib.tables._g_l_y_f import (
    USE_MY_METRICS, ROUND_XY_TO_GRID, UNSCALED_COMPONENT_OFFSET,
    SCALED_COMPONENT_OFFSET,
)


_use_my_metrics = r"^USEMYMETRICS\[\][\r\n]?"
_overlap = r"^OVERLAP\[\][\r\n]?"
_scaled_component_offset = r"^(?:UN)?SCALEDCOMPONENTOFFSET\[\][\r\n]?"
_anchor = r"^ANCHOR\[\](?:, *-?[0-9]+){3}[\r\n]?"
_offset = r"^OFFSET\[[rR]\](?:, *-?[0-9]+){3}[\r\n]?"
composite_info_RE = re.compile(
    "(%s)|(%s)|(%s)|(%s)|(%s)" % (
        _use_my_metrics, _overlap, _scaled_component_offset, _anchor, _offset
    ), re.MULTILINE
)


class VTTLibError(TTLibError):
    pass


class VTTLibInvalidComposite(VTTLibError):
    pass


def set_cvt_table(font, data):
    data = re.sub(r"/\*.*?\*/", "", data, flags=re.DOTALL)
    values = array.array(tostr("h"))
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


OffsetComponent = namedtuple('OffsetComponent', [
    'index', 'x', 'y', 'round_to_grid', 'use_my_metrics',
    'scaled_offset'])
AnchorComponent = namedtuple('AnchorComponent', [
    'index', 'first', 'second', 'use_my_metrics',
    'scaled_offset'])


def transform_assembly(data, components=None):
    tokens = AssemblyParser.parseString(data, parseAll=True)

    push_on = True
    push_indexes = [0]
    stream = [deque()]
    pos = 1
    if components is None:
        components = []
    round_to_grid = False
    use_my_metrics = False
    scaled_offset = None
    for t in tokens:
        mnemonic = t.mnemonic

        if mnemonic == "OVERLAP":
            # this component flag is ignored by VTT so we ignore it too
            continue
        elif mnemonic == "USEMYMETRICS":
            use_my_metrics = True
            continue
        elif mnemonic == "SCALEDCOMPONENTOFFSET":
            scaled_offset = True
            continue
        elif mnemonic == "UNSCALEDCOMPONENTOFFSET":
            scaled_offset = False
            continue
        elif mnemonic == "OFFSET":
            round_to_grid = t.flags == '1'
            index, x, y = t.stack_items
            component = OffsetComponent(
                index, x, y, round_to_grid, use_my_metrics, scaled_offset)
            components.append(component)
            use_my_metrics = round_to_grid = False
            scaled_offset = None
            continue
        elif mnemonic == "ANCHOR":
            index, first, second = t.stack_items
            component = AnchorComponent(
                index, first, second, use_my_metrics, scaled_offset)
            components.append(component)
            use_my_metrics = False
            scaled_offset = None

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

            deltas = OrderedDict()
            for point_index, rel_ppem, step_no in reversed(t.deltas):
                deltas.setdefault(point_index, []).append((rel_ppem, step_no))

            for point_index, delta_specs in deltas.items():
                for rel_ppem, step_no in sorted(delta_specs, reverse=True):
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

    return "\n".join([i for i in stream if i])


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


def make_program(vtt_assembly, name=None, components=None):
    try:
        ft_assembly = transform_assembly(vtt_assembly, components)
    except ParseException as e:
        import sys
        if name:
            sys.stderr.write(
                'An error occurred while parsing "%s" program:\n' % name)
        sys.stderr.write(e.markInputline() + "\n\n")
        raise VTTLibError(e)
    program = Program()
    program.fromAssembly(ft_assembly)
    # need to compile bytecode for PUSH optimization
    program._assemble()
    del program.assembly
    return program


def make_glyph_program(vtt_assembly, name=None):
    components = []
    program = make_program(vtt_assembly, name, components)
    return program, components


def get_extra_assembly(font, tag):
    if tag not in ("cvt", "cvt ", "prep", "ppgm", "fpgm"):
        raise ValueError("Invalid tag: %r" % tag)
    if tag == "prep":
        tag = "ppgm"
    return _get_assembly(font, tag.strip())


def get_glyph_assembly(font, name):
    return _get_assembly(font, name, is_glyph=True)


def _get_assembly(font, name, is_glyph=False):
    if 'TSI1' not in font:
        raise VTTLibError("TSI1 table not found")
    try:
        if is_glyph:
            data = font['TSI1'].glyphPrograms[name]
        else:
            data = font['TSI1'].extraPrograms[name]
    except KeyError:
        raise VTTLibError(
            "%s program missing from TSI1: '%s'" % (
                "Glyph" if is_glyph else "Extra", name))
    return tounicode(data.replace(b"\r", b"\n"), encoding='utf-8')


def set_glyph_assembly(font, name, data):
    _set_assembly(font, name, data, is_glyph=True)


def _set_assembly(font, name, data, is_glyph=False):
    if 'TSI1' not in font:
        raise VTTLibError("TSI1 table not found")
    data = tobytes(data, encoding='utf-8')
    data = b'\r'.join(data.splitlines()).rstrip() + b'\r'
    if is_glyph:
        font['TSI1'].glyphPrograms[name] = data
    else:
        font['TSI1'].extraPrograms[name] = data


def check_composite_info(name, glyph, vtt_components, glyph_order):
    n_glyf_comps = len(glyph.components)
    n_vtt_comps = len(vtt_components)
    if n_vtt_comps != n_glyf_comps:
        raise VTTLibInvalidComposite(
            "'%s' has incorrect number of components: expected %d, "
            "found %d." % (name, n_glyf_comps, n_vtt_comps))
    for i, comp in enumerate(glyph.components):
        vttcomp = vtt_components[i]
        base_name = comp.glyphName
        index = glyph_order.index(base_name)
        if vttcomp.index != index:
            raise VTTLibInvalidComposite(
                "Component %d in '%s' has incorrect index: "
                "expected %d, found %d." % (i, name, index, vttcomp.index))
        if hasattr(comp, 'firstPt'):
            if not hasattr(vttcomp, 'first') and hasattr(vttcomp, 'x'):
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has incorrect type: "
                    "expected ANCHOR[], found OFFSET[]." % (i, name))
            if comp.firstPt != vttcomp.first:
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has wrong anchor point: expected"
                    " %d, found %d." % (i, name, comp.firstPt, vttcomp.first))
            if comp.secondPt != vttcomp.second:
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has wrong anchor point: expected"
                    " %d, found %d." % (i, name, comp.secondPt, vttcomp.second))
        else:
            assert hasattr(comp, 'x')
            if not hasattr(vttcomp, 'x') and hasattr(vttcomp, 'first'):
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has incorrect type: "
                    "expected OFFSET[], found ANCHOR[]." % (i, name))
            if comp.x != vttcomp.x:
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has wrong x offset: expected"
                    " %d, found %d." % (i, name, comp.x, vttcomp.x))
            if comp.y != vttcomp.y:
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has wrong y offset: expected"
                    " %d, found %d." % (i, name, comp.y, vttcomp.y))
            if ((comp.flags & ROUND_XY_TO_GRID and
                    not vttcomp.round_to_grid) or
                    (not comp.flags & ROUND_XY_TO_GRID and
                     vttcomp.round_to_grid)):
                raise VTTLibInvalidComposite(
                    "Component %d in '%s' has wrong 'ROUND_XY_TO_GRID' flag."
                    % (i, name))
        if ((comp.flags & USE_MY_METRICS and not vttcomp.use_my_metrics) or
                (not comp.flags & USE_MY_METRICS and vttcomp.use_my_metrics)):
            raise VTTLibInvalidComposite(
                "Component %d in '%s' has wrong 'USE_MY_METRICS' flag."
                % (i, name))
        if ((comp.flags & SCALED_COMPONENT_OFFSET and
                not vttcomp.scaled_offset) or
                (not comp.flags & SCALED_COMPONENT_OFFSET and
                 vttcomp.scaled_offset)):
            raise VTTLibInvalidComposite(
                "Component %d in '%s' has wrong 'SCALED_COMPONENT_OFFSET' flag."
                % (i, name))
        if ((comp.flags & UNSCALED_COMPONENT_OFFSET and
                not vttcomp.scaled_offset) or
                (not comp.flags & UNSCALED_COMPONENT_OFFSET and
                 vttcomp.scaled_offset)):
            raise VTTLibInvalidComposite(
                "Component %d in '%s' has wrong 'UNSCALED_COMPONENT_OFFSET' flag."
                "flag" % (i, name))


def write_composite_info(glyph, glyph_order, data="", vtt_version=6):
    head = ""
    last = 0
    for m in composite_info_RE.finditer(data):
        start, end = m.span()
        head += data[last:start]
        last = end
    tail = ""
    if last < len(data):
        tail += data[last:]
    instructions = []
    for comp in glyph.components:
        if comp.flags & USE_MY_METRICS:
            instructions.append("USEMYMETRICS[]\n")
        if vtt_version >= 6:
            if comp.flags & SCALED_COMPONENT_OFFSET:
                instructions.append("SCALEDCOMPONENTOFFSET[]\n")
            if comp.flags & UNSCALED_COMPONENT_OFFSET:
                instructions.append("UNSCALEDCOMPONENTOFFSET[]\n")
        index = glyph_order.index(comp.glyphName)
        if hasattr(comp, 'firstPt'):
            instructions.append("ANCHOR[], %d, %d, %d\n"
                                % (index, comp.firstPt, comp.secondPt))
        else:
            flag = "R" if comp.flags & ROUND_XY_TO_GRID else "r"
            instructions.append(
                "OFFSET[%s], %d, %d, %d\n" % (flag, index, comp.x, comp.y))
    return head + "".join(instructions) + tail


def update_composites(font, glyphs=None, vtt_version=6):
    glyph_order = font.getGlyphOrder()
    if glyphs is None:
        glyphs = glyph_order
    glyf_table = font['glyf']
    for glyph_name in glyphs:
        glyph = glyf_table[glyph_name]
        if not glyph.isComposite():
            continue
        data = get_glyph_assembly(font, glyph_name)
        new_data = write_composite_info(glyph, glyph_order, data, vtt_version)
        set_glyph_assembly(font, glyph_name, new_data)


def compile_instructions(font, ship=True):
    if "glyf" not in font:
        raise VTTLibError("Missing 'glyf' table; not a TrueType font")
    if "TSI1" not in font:
        raise VTTLibError("The font contains no 'TSI1' table")

    control_program = get_extra_assembly(font, "cvt")
    set_cvt_table(font, control_program)

    for tag in ("prep", "fpgm"):
        if tag not in font:
            font[tag] = newTable(tag)
        data = get_extra_assembly(font, tag)
        font[tag].program = make_program(data, tag)

    glyph_order = font.getGlyphOrder()
    glyf_table = font['glyf']
    for glyph_name in glyph_order:
        try:
            data = get_glyph_assembly(font, glyph_name)
        except KeyError:
            continue
        program, components = make_glyph_program(data, glyph_name)
        if program or components:
            glyph = glyf_table[glyph_name]
            if components:
                check_composite_info(
                    glyph_name, glyph, components, glyph_order)
            if program:
                glyph.program = program

    if ship:
        for tag in ("TSI%d" % i for i in (0, 1, 2, 3, 5)):
            if tag in font:
                del font[tag]
