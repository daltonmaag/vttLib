import io
import logging

import fontTools
import fontTools.ttLib
import vttLib

logger = logging.Logger(__name__)


def dump_to_lib_keys(font, ufo):
    if font.sfntVersion not in ("\x00\x01\x00\x00", "true"):
        raise vttLib.VTTLibArgumentError("Not a TrueType font (bad sfntVersion)")

    for table_tag in ("TSI1", "TSI3", "TSI5"):
        if table_tag not in font:
            raise vttLib.VTTLibArgumentError(
                "Table '%s' not found in input font" % table_tag
            )

    vttLib.normalize_vtt_programs(font)
    vttLib.subset_vtt_glyph_programs(font, [g.name for g in ufo])

    font_tsi1 = font["TSI1"]
    for extra_program in vttLib.TSI1_EXTRA_PROGRAMS:
        if extra_program in font_tsi1.extraPrograms:
            lib_key = f"com.daltonmaag.vttLib.tsi1.{extra_program}"
            ufo.lib[lib_key] = font_tsi1.extraPrograms[extra_program]

    font_maxp = font["maxp"]
    for attr in vttLib.MAXP_ATTRS:
        lib_key = f"{vttLib.MAXP_KEY}.{attr}"
        ufo.lib[lib_key] = vars(font_maxp)[attr]

    ufo.lib["com.daltonmaag.vttLib.tsi5.glyphGrouping"] = font["TSI5"].glyphGrouping

    font_tsi1_glyphs = font_tsi1.glyphPrograms
    glyph_tsi1_key = "com.daltonmaag.vttLib.tsi1.glyphProgram"
    for glyph_name, data in font_tsi1_glyphs.items():
        if glyph_name in ufo:
            ufo[glyph_name].lib[glyph_tsi1_key] = data
        else:
            logger.warning(
                f"TSI1 table contains code for glyph '{glyph_name}' that is not in UFO '{ufo.path}'"
            )

    font_tsi3_glyphs = font["TSI3"].glyphPrograms
    glyph_tsi3_key = "com.daltonmaag.vttLib.tsi3.glyphProgram"
    for glyph_name, data in font_tsi3_glyphs.items():
        if glyph_name in ufo:
            ufo[glyph_name].lib[glyph_tsi3_key] = data
        else:
            logger.warning(
                f"TSI3 table contains code for glyph '{glyph_name}' that is not in UFO '{ufo.path}'"
            )


def merge_from_lib_keys(ufo, font):
    if font.sfntVersion not in ("\x00\x01\x00\x00", "true"):
        raise VTTLibArgumentError("Not a TrueType font (bad sfntVersion)")

    if "TSI1" not in font:
        font["TSI0"] = fontTools.ttLib.newTable("TSI0")
        font["TSI1"] = fontTools.ttLib.newTable("TSI1")
        font["TSI1"].glyphPrograms = {}
        font["TSI1"].extraPrograms = {}

    font_tsi1 = font["TSI1"]
    for extra_program in vttLib.TSI1_EXTRA_PROGRAMS:
        lib_key = f"com.daltonmaag.vttLib.tsi1.{extra_program}"
        if lib_key in ufo.lib:
            font_tsi1.extraPrograms[extra_program] = ufo.lib[lib_key]

    if "TSI3" not in font:
        font["TSI2"] = fontTools.ttLib.newTable("TSI2")
        font["TSI3"] = fontTools.ttLib.newTable("TSI3")
        font["TSI3"].glyphPrograms = {}
        font["TSI3"].extraPrograms = {}

    font_tsi3 = font["TSI3"]
    glyph_tsi1_key = "com.daltonmaag.vttLib.tsi1.glyphProgram"
    glyph_tsi3_key = "com.daltonmaag.vttLib.tsi3.glyphProgram"
    for glyph in ufo:
        if glyph_tsi1_key in glyph.lib:
            font_tsi1.glyphPrograms[glyph.name] = glyph.lib[glyph_tsi1_key]
        if glyph_tsi3_key in glyph.lib:
            font_tsi3.glyphPrograms[glyph.name] = glyph.lib[glyph_tsi3_key]

    if "TSI5" not in font:
        font["TSI5"] = fontTools.ttLib.newTable("TSI5")
        font["TSI5"].glyphGrouping = {}

    if "com.daltonmaag.vttLib.tsi5.glyphGrouping" in ufo.lib:
        font["TSI5"].glyphGrouping = ufo.lib["com.daltonmaag.vttLib.tsi5.glyphGrouping"]

    font_maxp = font["maxp"]
    for attr in vttLib.MAXP_ATTRS:
        lib_key = f"{vttLib.MAXP_KEY}.{attr}"
        if lib_key in ufo.lib:
            vars(font_maxp)[attr] = ufo.lib[lib_key]


def merge_from_data_files(ufo, font):
    for key, data in ufo.data.items():
        if "T_S_I__" in key:
            font.importXML(io.BytesIO(data))
        else:
            data_maxp = fontTools.misc.plistlib.loads(data)["maxp"]
            maxp = font["maxp"]
            for name in vttLib.MAXP_ATTRS:
                if name in data_maxp:
                    value = data_maxp[name]
                    setattr(maxp, name, value)


def data_files_to_lib_keys(ufo):
    font = fontTools.ttLib.TTFont()
    font["maxp"] = maxp = fontTools.ttLib.newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max(len(g.components) for g in ufo)
    maxp.numGlyphs = len(ufo)
    merge_from_data_files(ufo, font)
    dump_to_lib_keys(font, ufo)


def clean_vtt_data_files(ufo):
    for unwanted_data in vttLib.LEGACY_VTT_DATA_FILES:
        if unwanted_data in ufo.data:
            del ufo.data[unwanted_data]
