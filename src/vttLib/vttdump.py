from __future__ import print_function, absolute_import, unicode_literals
import sys
import os
import errno
import argparse
import plistlib
import re
import logging

from fontTools.ttLib import TTFont
from fontTools.misc.py23 import tounicode, tobytes

try:
    import ufonormalizer
except:
    ufonormalizer = None


TTX_DATA_FOLDER = "org.fonttools.ttx"
VTT_TABLES = ["TSI0", "TSI1", "TSI2", "TSI3", "TSI5"]
MAXP_KEY = 'com.robofont.robohint.maxp'
MAXP_ATTRS = {
    'maxZones',
    'maxTwilightPoints',
    'maxStorage',
    'maxFunctionDefs',
    'maxInstructionDefs',
    'maxStackElements',
    'maxSizeOfInstructions',
}

comment_re = r'/\*%s\*/[\r\n]*'
# strip the timestamps
gui_generated_re = re.compile(comment_re % (r' GUI generated .*?'))
vtt_compiler_re = re.compile(
    comment_re % (r' (VTT [0-9]+\.[0-9][0-9A-Z]* compiler) .*?'))
# strip glyph indexes
glyph_re = re.compile(comment_re % (r' (?:TT|VTTTalk) glyph [0-9]+.*?'))


if hasattr(plistlib, "load"):
    # PY3
    def _read_plist(path):
        with open(path, 'rb') as fp:
            return plistlib.load(fp)

    def _write_plist(value, path):
        with open(path, 'wb') as fp:
            plistlib.dump(value, fp)
else:
    # PY2
    _read_plist = plistlib.readPlist
    _write_plist = plistlib.writePlist


def normalize_vtt_programs(font):
    for tag in font["TSI1"].extraPrograms:
        program = tounicode(font["TSI1"].extraPrograms[tag], encoding='utf-8')
        program = vtt_compiler_re.sub(r'/* \1 */\r', program)
        # VTT uses Macintosh newlines
        program = '\r'.join(program.splitlines()).rstrip() + '\r'
        font["TSI1"].extraPrograms[tag] = tobytes(program, encoding='utf-8')

    glyph_order = font.getGlyphOrder()
    for glyph in glyph_order:
        for tag in ("TSI1", "TSI3"):
            if glyph in font[tag].glyphPrograms:
                program = tounicode(
                    font[tag].glyphPrograms[glyph], encoding='utf-8')
                program = gui_generated_re.sub('', program)
                # keep the VTT version
                program = vtt_compiler_re.sub(r'/* \1 */\r', program)
                program = glyph_re.sub('', program)
                program = '\r'.join(program.splitlines()).rstrip() + '\r'
                font[tag].glyphPrograms[glyph] = tobytes(program,
                                                         encoding='utf-8')
    if len(font['TSI3'].extraPrograms):
        # VTT sometimes stores 'reserved' data in TSI3 which isn't needed
        font['TSI3'].extraPrograms = {}


def write_maxp_data(font, ufo):
    libfilename = os.path.join(ufo, "lib.plist")
    try:
        lib = _read_plist(libfilename)
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        lib = {}  # lib.plist file is optional
    maxp = font['maxp']
    for name in MAXP_ATTRS:
        lib[MAXP_KEY + "." + name] = getattr(maxp, name)
    _write_plist(lib, libfilename)
    if ufonormalizer:
        ufonormalizer.normalizeLibPlist(ufo)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Dumps VTT tables (TSI1, TSI3 and TSI5) and maxp data to "
        "UFO3 font.")
    parser.add_argument('infile', metavar='font.ttf',
                        help='the input font file')
    parser.add_argument('-u', '--ufo', metavar='font.ufo',
                        dest='ufo', help='the path to the UFO where to dump the'
                        ' TTX files.')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-v', '--verbose', action='store_true', help='print '
                       'more messages to console.')
    group.add_argument('-q', '--quiet', action='store_true', help='do not '
                       'print messages to console.')
    options = parser.parse_args(args)

    logging.basicConfig(
        level=("ERROR" if options.quiet else
               "DEBUG" if options.verbose else "INFO"),
        format="%(message)s")

    font = TTFont(options.infile)

    if font.sfntVersion not in ("\x00\x01\x00\x00", "true"):
        parser.error("Not a TrueType font (bad sfntVersion)")
    for table_tag in VTT_TABLES:
        if table_tag not in font:
            parser.error("Table '%s' not found in input font" % table_tag)

    if not options.ufo:
        ufo = os.path.splitext(options.infile)[0] + ".ufo"
        if not os.path.exists(ufo):
            parser.error("'%s' not found; try with -u option" % ufo)
    else:
        ufo = options.ufo
        if not os.path.exists(ufo) or not os.path.isdir(ufo):
            parser.error("No such directory: '%s'" % ufo)

    try:
        metainfo = _read_plist(os.path.join(ufo, "metainfo.plist"))
        ufo_version = int(metainfo["formatVersion"])
    except (IOError, KeyError, ValueError) as e:
        parser.error("Not a valid UFO file: %s" % e)
    else:
        if ufo_version < 3:
            parser.error("Unsupported UFO format: %d" % ufo_version)

    folder = os.path.join(ufo, "data", TTX_DATA_FOLDER)
    # create data sub-folder if it's not there already
    try:
        os.makedirs(folder)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(folder):
            raise
    # path to the TTX index file, pointing to individual split *.ttx tables
    outfile = os.path.join(folder, "font.ttx")

    normalize_vtt_programs(font)

    write_maxp_data(font, ufo)

    font.saveXML(outfile, tables=VTT_TABLES, splitTables=True)


if __name__ == "__main__":
    sys.exit(main())
