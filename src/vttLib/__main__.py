from __future__ import print_function, division, absolute_import
import sys
from argparse import ArgumentParser, _VersionAction
import logging

from vttLib import vtt_compile, vtt_dump, vtt_merge, VTTLibArgumentError


class PkgVersionAction(_VersionAction):

    def __call__(self, parser, namespace, values, option_string=None):
        import pkg_resources
        self.version = pkg_resources.get_distribution("vttLib").version
        super(PkgVersionAction, self).__call__(
            parser, namespace, values, option_string)


def main(args=None):
    parser = ArgumentParser(
        prog="python -m vttLib", description="Dump, merge or compile Visual "
        "TrueType data in UFO3 with FontTools")
    parser.add_argument('--version', action=PkgVersionAction)

    parser_group = parser.add_subparsers(title="sub-commands")

    parser_dump = parser_group.add_parser(
        'dump', help="export VTT tables and 'maxp' values from TTF to UFO",
        description="Dump VTT tables as TTX files to UFO3 'data' folder.")
    parser_merge = parser_group.add_parser(
        'merge', help="import VTT source data stored in UFO to TTF",
        description="Merge VTT tables from UFO3 'data' folder to TTF font.")
    parser_compile = parser_group.add_parser(
        'compile', help="generate TrueType bytecode from VTT assembly",
        description="Generate 'fpgm', 'prep', 'cvt ' and 'glyf' programs from "
        "VTT assembly.")
    subparsers = (parser_compile, parser_dump, parser_merge)

    for subparser in subparsers:
        group = subparser.add_mutually_exclusive_group(required=False)
        group.add_argument('-v', '--verbose', action='store_true', help='print '
                           'more messages to console')
        group.add_argument('-q', '--quiet', action='store_true', help='do not '
                           'print messages to console')

    parser_merge.add_argument(
        'infile', metavar='INPUT.ufo', help='the source UFO font containing '
        'VTT TSI* tables in .ttx format')
    for subparser in (parser_compile, parser_dump):
        subparser.add_argument(
            'infile', metavar='INPUT.ttf', help='the source TTF font '
            'containing VTT TSI* tables')

    parser_dump.add_argument(
        'outfile', nargs='?', metavar='OUTPUT.ufo', help='the destination '
        'UFO where to dump the VTT tables (default: INPUT + ".ufo")')
    parser_merge.add_argument(
        'outfile', nargs='?', metavar='OUTPUT.ttf', help='the TTF to merge '
        'data with (default: INPUT + ".ttf")')

    output_group = parser_compile.add_mutually_exclusive_group()
    output_group.add_argument(
        'outfile', nargs='?', metavar='OUTPUT.ttf', help='the destination TTF'
        ' with compiled TrueType bytecode (default: '
        'INTPUT + "#{n}.ttf").')
    output_group.add_argument(
        '-i', '--inplace', metavar=".bak", help="save input file in place, "
        "and create backup with specified extension")
    output_group.add_argument(
        '-f', '--force-overwrite', action='store_true',
        help="overwrite existing input file (CAUTION!)")

    parser_compile.add_argument(
        '--ship', action='store_true', help='remove all the TSI* tables from '
        'the output font.')

    parser_compile.set_defaults(func=vtt_compile)
    parser_merge.set_defaults(func=vtt_merge)
    parser_dump.set_defaults(func=vtt_dump)

    options = parser.parse_args(args)

    logging.basicConfig(
        level=("ERROR" if options.quiet else
               "DEBUG" if options.verbose else "INFO"),
        format="%(message)s")

    try:
        options.func(**vars(options))
    except VTTLibArgumentError as e:
        parser.error(e)


if __name__ == "__main__":
    sys.exit(main())
