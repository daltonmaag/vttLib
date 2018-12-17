import fontTools.ttLib
import pytest
import ufo2ft
import ufoLib2

import vttLib
import vttLib.transfer


@pytest.fixture
def test_ufo_UbuTestData(original_shared_datadir):
    font = ufoLib2.Font.open(original_shared_datadir / "UbuTestData.ufo")
    return font


def test_dump_data_to_lib_keys(tmp_path, test_ufo_UbuTestData):
    ufo = test_ufo_UbuTestData
    ufo_path = tmp_path / "UbuntuTestData.ufo"
    font = ufo2ft.compileTTF(ufo)
    ufo.save(ufo_path)
    font_path = tmp_path / "UbuntuTestData.ttf"
    font.save(font_path)

    vttLib.vtt_merge(ufo_path, font_path)
    vttLib.vtt_dump(font_path, ufo_path)
    font_merged = fontTools.ttLib.TTFont(font_path)
    ufo_rt = ufoLib2.Font.open(ufo_path)
    _test_roundtrip(font_merged, ufo_rt)


def test_merge_data_from_lib_keys(tmp_path, test_ufo_UbuTestData):
    ufo = test_ufo_UbuTestData
    vttLib.transfer.data_files_to_lib_keys(ufo)
    vttLib.transfer.clean_vtt_data_files(ufo)
    ufo_path = tmp_path / "UbuntuTestData.ufo"
    ufo.save(ufo_path)
    font = ufo2ft.compileTTF(ufo)
    font_path = tmp_path / "UbuntuTestData.ttf"
    font.save(font_path)
    vttLib.vtt_merge(ufo_path, font_path)

    font_merged = fontTools.ttLib.TTFont(font_path)
    ufo_rt = ufoLib2.Font.open(ufo_path)
    _test_roundtrip(font_merged, ufo_rt)


def _test_roundtrip(font, ufo):
    font_tsi1_extra = font["TSI1"].extraPrograms
    assert ufo.lib["com.daltonmaag.vttLib.tsi1.cvt"] == font_tsi1_extra["cvt"]
    assert ufo.lib["com.daltonmaag.vttLib.tsi1.fpgm"] == font_tsi1_extra["fpgm"]
    assert ufo.lib["com.daltonmaag.vttLib.tsi1.ppgm"] == font_tsi1_extra["ppgm"]

    for attr in vttLib.MAXP_ATTRS:
        lib_key = f"com.robofont.robohint.maxp.{attr}"
        assert ufo.lib[lib_key] == vars(font["maxp"])[attr]

    glyph_grouping = font["TSI5"].glyphGrouping
    for key, value in ufo.lib["com.daltonmaag.vttLib.tsi5.glyphGrouping"].items():
        assert glyph_grouping[key] == value

    font_tsi1_glyphs = font["TSI1"].glyphPrograms
    glyph_tsi1_key = "com.daltonmaag.vttLib.tsi1.glyphProgram"
    font_tsi3_glyphs = font["TSI3"].glyphPrograms
    glyph_tsi3_key = "com.daltonmaag.vttLib.tsi3.glyphProgram"

    for glyph in ufo:
        if glyph.name in font_tsi1_glyphs:
            glyph.lib[glyph_tsi1_key] == font_tsi1_glyphs[glyph.name]
        if glyph.name in font_tsi3_glyphs:
            glyph.lib[glyph_tsi3_key] == font_tsi3_glyphs[glyph.name]

    for unwanted_data in vttLib.LEGACY_VTT_DATA_FILES:
        assert unwanted_data not in ufo.data.keys()
