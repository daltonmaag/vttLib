from __future__ import print_function, division, absolute_import
import sys
from fontTools.ttLib import TTFont, TTLibError
from fontTools.ttx import makeOutputFileName
from vttLib import (
    VTTLibInvalidComposite, VTTLibError, compile_instructions,
    update_composite_info,
)
import argparse


def parse_arguments(args):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="vttLib", description="Compile VTT assembly to TrueType bytecode "
        "with FontTools")
    parser.add_argument('infile', metavar='INPUT.ttf', help='the intput font '
                        'containing TSI1 private table')
    parser.add_argument('outfile', metavar='OUTPUT.ttf', nargs="?",
                        help='the output font with compiled TrueType '
                        'instructions.')
    parser.add_argument('--update-composites', action='store_true', help="sync"
                        "hronize indexes, flags and offsets of components in "
                        "TSI1 programs with the data from the 'glyf' table")
    parser.add_argument('--ship', action='store_true', help='remove '
                        'all the TSI* tables from the output font.')

    options = parser.parse_args(args)
    if not options.outfile:
        options.outfile = makeOutputFileName(options.infile, None, ".ttf")
    return options


def main(args=None):
    options = parse_arguments(args)

    font = TTFont(options.infile)

    try:
        if options.update_composites:
            update_composite_info(font)
        try:
            compile_instructions(font, ship=options.ship)
        except VTTLibInvalidComposite as e:
            if options.update_composites:
                raise RuntimeError("Unexpected error: %s" % e)
            else:
                raise VTTLibError(
                    "Composite glyphs data in VTT source don't match the "
                    "'glyf' table:\n%s\nTry running with --update-composites"
                    " option." % e)
    except VTTLibError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    else:
        font.save(options.outfile)


if __name__ == "__main__":
    main()
