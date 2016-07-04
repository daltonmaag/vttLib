from __future__ import print_function, division, absolute_import
import sys
from fontTools.ttLib import TTFont, TTLibError
from fontTools.ttx import makeOutputFileName
from vttLib import compile_instructions
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
        compile_instructions(font, ship=options.ship)
    except TTLibError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    else:
        font.save(options.outfile)


main()
