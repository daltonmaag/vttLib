import io
import logging
import os

import fontTools
import fontTools.ttLib

import vttLib

logger = logging.Logger(__name__)


def dump_to_file(font: fontTools.ttLib.TTFont, path: os.PathLike):
    """Dump relevant VTT data to a file.

    Relevant are:
    - TSI1 holds the assembly code
    - TSI3 holds the VTT code
    - TSI5 holds glyph group information
    - maxp holds instruction data computed by VTT, among other data

    TSI0 and TSI2 are filled in by fontTools.
    """
    TABLES_TO_DUMP = ("TSI1", "TSI3", "TSI5", "maxp")
    for table_tag in TABLES_TO_DUMP:
        if table_tag not in font:
            raise vttLib.VTTLibArgumentError(
                "Table '%s' not found in input font" % table_tag
            )

    vttLib.normalize_vtt_programs(font)
    font.saveXML(path, tables=TABLES_TO_DUMP)


def merge_from_file(font: fontTools.ttLib.TTFont, path: os.PathLike):
    """Merge VTT data from TTX dump into TTFont object.

    The 'maxp' table is only partially merged, as we want to import only data
    related to TrueType instructions, so it needs to pre-exist.
    """
    if "maxp" not in font:
        raise vttLib.VTTLibArgumentError("'maxp' table not found in target font.")

    ttx_dump = fontTools.ttLib.TTFont()
    ttx_dump.importXML(path)  # Import here so we can selectively merge maxp into font.
    ttx_dump["TSI0"] = fontTools.ttLib.newTable("TSI0")
    ttx_dump["TSI2"] = fontTools.ttLib.newTable("TSI2")

    for tsi_table in ("TSI0", "TSI1", "TSI2", "TSI3", "TSI5"):
        font[tsi_table] = ttx_dump[tsi_table]

    for maxp_attr in vttLib.MAXP_ATTRS:
        setattr(font["maxp"], maxp_attr, getattr(ttx_dump["maxp"], maxp_attr))


def copy_from_ufo_data_to_file(ufo, path: os.PathLike):
    """Dump VTT data stored in a UFO's data/ structure into a file.

    This is used to convert data from Legacy Projects to The New Way.
    """
    font = fontTools.ttLib.TTFont()

    font["maxp"] = maxp = fontTools.ttLib.newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxComponentDepth = 0
    maxp.maxComponentElements = max(len(g.components) for g in ufo)
    maxp.maxCompositeContours = 0
    maxp.maxCompositePoints = 0
    maxp.maxContours = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxPoints = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxStackElements = 0
    maxp.maxStorage = 0
    maxp.maxTwilightPoints = 0
    maxp.maxZones = 1
    maxp.numGlyphs = len(ufo)
    if ".notdef" not in ufo:
        maxp.numGlyphs += 1

    for key, data in ufo.data.items():
        if "T_S_I__" in key:
            font.importXML(io.BytesIO(data))
        if "com.daltonmaag.vttLib" in key:
            data_maxp = fontTools.misc.plistlib.loads(data)["maxp"]
            maxp = font["maxp"]
            for name in vttLib.MAXP_ATTRS:
                if name in data_maxp:
                    value = data_maxp[name]
                    setattr(maxp, name, value)

    dump_to_file(font, path)
