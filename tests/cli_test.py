import shutil
from pathlib import Path

import fontTools.ttLib
import pytest
import ufo2ft
import ufoLib2

import vttLib
import vttLib.__main__


@pytest.fixture
def test_ufo_UbuTestData(original_shared_datadir):
    font = ufoLib2.Font.open(original_shared_datadir / "UbuTestData.ufo")
    return font


def test_move_ufo_data_to_file_and_roundtrip(tmp_path, test_ufo_UbuTestData):
    ufo = test_ufo_UbuTestData
    ufo_path = tmp_path / "UbuntuTestData.ufo"
    ufo.save(ufo_path)
    test_ttf_path = tmp_path / "test.ttf"
    test_ttx_path = tmp_path / "test.ttx"

    vttLib.__main__.main(["dumpfile_from_ufo", str(ufo_path), str(test_ttx_path)])
    ### Doctor TTX dump so the simple text compare further down works
    _ttx_dump = fontTools.ttLib.TTFont()
    _ttx_dump.importXML(test_ttx_path)
    _ttx_dump["maxp"].maxPoints = 54
    _ttx_dump["maxp"].maxContours = 2
    _ttx_dump.saveXML(test_ttx_path, tables=("TSI1", "TSI3", "TSI5", "maxp"))
    ###
    ufo_tmp = ufoLib2.Font.open(ufo_path)

    for legacy_data in vttLib.LEGACY_VTT_DATA_FILES:
        assert legacy_data in ufo_tmp.data.keys()

    ttx_dump = fontTools.ttLib.TTFont()
    ttx_dump.importXML(test_ttx_path)
    assert ttx_dump["maxp"].maxFunctionDefs == 89
    assert ttx_dump["maxp"].maxInstructionDefs == 0
    assert ttx_dump["maxp"].maxSizeOfInstructions == 1571
    assert ttx_dump["maxp"].maxStackElements == 542
    assert ttx_dump["maxp"].maxStorage == 47
    assert ttx_dump["maxp"].maxTwilightPoints == 16
    assert ttx_dump["maxp"].maxZones == 2

    ttf = ufo2ft.compileTTF(ufo_tmp)
    ttf.save(test_ttf_path)
    vttLib.__main__.main(["mergefile", str(test_ttx_path), str(test_ttf_path)])
    vttLib.__main__.main(["dumpfile", str(test_ttf_path), str(tmp_path / "test2.ttx")])

    # Cut out the first two lines with version information for the comparison.
    dump_before = Path(tmp_path / "test.ttx").read_text().split("\n", 2)[-1]
    dump_after = Path(tmp_path / "test2.ttx").read_text().split("\n", 2)[-1]
    assert dump_before == dump_after

    vttLib.__main__.main(["compile", str(test_ttf_path), str(test_ttf_path), "--ship"])
    ttf = fontTools.ttLib.TTFont(test_ttf_path)
    assert "fpgm" in ttf
    assert "TSI1" not in ttf


def test_roundtrip_TSIC_cvar(tmp_path: Path, original_shared_datadir: Path) -> None:
    font_file = original_shared_datadir / "NotoSans-MM-ASCII-VF.ttf"
    font_file_tmp = tmp_path / "NotoSans-MM-ASCII-VF.ttf"
    font_file_vtt = original_shared_datadir / "NotoSans-MM-ASCII-VF.ttx"
    font_file_vtt_tmp = tmp_path / "NotoSans-MM-ASCII-VF.ttx"
    shutil.copyfile(font_file, font_file_tmp)

    vttLib.__main__.main(["mergefile", str(font_file_vtt), str(font_file_tmp)])

    font = fontTools.ttLib.TTFont(font_file_tmp)
    assert "TSIC" in font
    assert "cvar" in font

    vttLib.__main__.main(["dumpfile", str(font_file_tmp), str(font_file_vtt_tmp)])
    # Cut out the first two lines with version information for the comparison.
    dump_before = font_file_vtt.read_text().split("\n", 2)[-1]
    dump_after = font_file_vtt_tmp.read_text().split("\n", 2)[-1]
    assert dump_before == dump_after

    vttLib.__main__.main(["compile", str(font_file_tmp), str(font_file_tmp), "--ship"])
    font = fontTools.ttLib.TTFont(font_file_tmp)
    assert "fpgm" in font
    assert "cvar" in font
    assert "cvt " in font
    assert "TSI1" not in font
    assert "TSIC" not in font


def test_maxp_selective_loading(tmp_path: Path, original_shared_datadir: Path) -> None:
    font_file = original_shared_datadir / "NotoSans-MM-ASCII-VF.ttf"
    font_file_tmp = tmp_path / "NotoSans-MM-ASCII-VF.ttf"
    font_file_vtt = original_shared_datadir / "NotoSans-MM-ASCII-VF_wrong_maxp.ttx"
    shutil.copyfile(font_file, font_file_tmp)

    vttLib.__main__.main(["mergefile", str(font_file_vtt), str(font_file_tmp)])

    font = fontTools.ttLib.TTFont(font_file_tmp)
    assert font["maxp"].maxComponentDepth == 0
    assert font["maxp"].maxComponentElements == 0
    assert font["maxp"].maxCompositeContours == 0
    assert font["maxp"].maxCompositePoints == 0
    assert font["maxp"].maxContours == 5
    assert font["maxp"].maxFunctionDefs == 9999
    assert font["maxp"].maxInstructionDefs == 9999
    assert font["maxp"].maxPoints == 78
    assert font["maxp"].maxSizeOfInstructions == 9999
    assert font["maxp"].maxStackElements == 9999
    assert font["maxp"].maxStorage == 9999
    assert font["maxp"].maxTwilightPoints == 9999
    assert font["maxp"].maxZones == 9999
    assert font["maxp"].numGlyphs == 96
