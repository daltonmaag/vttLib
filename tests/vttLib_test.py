import os
import shutil
from textwrap import dedent

import pytest
from fontTools.ttLib import TTFont

from vttLib import (
    make_ft_program,
    pformat_tti,
    transform_assembly,
    vtt_compile,
    vtt_merge_file,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")


TEST_NAMES = ["fdef83", "fdef133", "fdef152", "fdef153", "idef145", "pushoff_pushes"]


@pytest.fixture(params=TEST_NAMES)
def test_name(request):
    return request.param


@pytest.fixture()
def input_and_expected(request, test_name):
    inpuf_filename = test_name + ".txt"
    with open(os.path.join(DATA_DIR, inpuf_filename)) as fp:
        input_vtt_assembly = fp.read()

    expected_filename = test_name + "_transformed.txt"
    with open(os.path.join(DATA_DIR, expected_filename)) as fp:
        expected_ft_assembly = fp.read()
    ft_program = make_ft_program(expected_ft_assembly)
    expected_ft_assembly = pformat_tti(ft_program)

    return input_vtt_assembly, expected_ft_assembly


class TestTransformAssembly(object):
    def test_empty(self):
        assert not transform_assembly("")

    def test_ignore_overlap(self):
        ft_assembly = transform_assembly("OVERLAP[]")
        assert not ft_assembly

    def test_jump_back(self):
        vtt_assembly = dedent(
            """
            #PUSH, 1
            DUP[]
            #Label1:
            DUP[]
            DUP[]
            DUP[]
            #PUSH, Var1
            JMPR[], (Var1=#Label1)
            """
        )

        ft_assembly = transform_assembly(vtt_assembly)

        assert (
            ft_assembly
            == dedent(
                """
                PUSH[] 1
                DUP[]
                DUP[]
                DUP[]
                DUP[]
                PUSHW[] -6
                JMPR[]
                """
            ).strip()
        )

    def test_jump_forward(self):
        vtt_assembly = dedent(
            """
            #PUSH, Var1
            JMPR[], (Var1=#Label1)
            DUP[]
            DUP[]
            #PUSH, 1, 2
            DUP[]
            #Label1:
            DUP[]
            DUP[]
            """
        )

        ft_assembly = transform_assembly(vtt_assembly)

        assert (
            ft_assembly
            == dedent(
                """
                PUSHW[] 7
                JMPR[]
                DUP[]
                DUP[]
                PUSH[] 1 2
                DUP[]
                DUP[]
                DUP[]
                """
            ).strip()
        )

    def test_jump_mixed_args(self):
        vtt_assembly = dedent(
            """
            #PUSH, Var1, 1
            JROT[], (Var1=#Label1)
            DUP[]
            DUP[]
            DUP[]
            #Label1:
            DUP[]
            """
        )

        ft_assembly = transform_assembly(vtt_assembly)

        assert (
            ft_assembly
            == dedent(
                """
                PUSHW[] 4
                PUSH[] 1
                JROT[]
                DUP[]
                DUP[]
                DUP[]
                DUP[]
                """
            ).strip()
        )

    def test_jump_repeated_args(self):

        vtt_assembly = dedent(
            """
            #PUSH, 0, Var1, Var1, -1
            POP[]
            SWAP[]
            JROF[], (Var1=#Label1)
            DUP[]
            DUP[]
            #Label1:
            DUP[]
            """
        )

        ft_assembly = transform_assembly(vtt_assembly)

        assert (
            ft_assembly
            == dedent(
                """
                PUSH[] 0
                PUSHW[] 3 3
                PUSH[] -1
                POP[]
                SWAP[]
                JROF[]
                DUP[]
                DUP[]
                DUP[]
                """
            ).strip()
        )

    def test_delta_args_sorting(self):

        vtt_assembly = dedent(
            """
            DLTC1[(4 @4 8) (4 @8 8) (4 @11 8) (4 @15 8) (5 @4 8) (5 @8 8) (5 @11 8) (5 @15 8) (12 @1 8) (12 @4 8) (12 @5 8) (12 @8 8) (12 @9 8) (12 @13 8) (12 @15 8) (12 @0 8) (13 @1 8) (13 @4 8) (13 @5 8) (13 @8 8) (13 @9 8) (13 @13 8) (13 @15 8) (13 @0 8) (14 @11 8) (14 @13 8) (14 @15 8) (15 @11 8) (15 @13 8) (15 @15 8)]
            DLTC2[(4 @3 8) (4 @6 8) (4 @7 8) (4 @10 8) (4 @14 8) (5 @3 8) (5 @6 8) (5 @7 8) (5 @10 8) (5 @14 8) (12 @1 8) (12 @3 8) (12 @4 8) (12 @5 8) (12 @9 8) (12 @13 8) (13 @1 8) (13 @3 8) (13 @4 8) (13 @5 8) (13 @9 8) (13 @13 8) (14 @1 8) (14 @3 8) (14 @5 8) (14 @7 8) (14 @9 8) (14 @11 8) (14 @13 8) (15 @1 8) (15 @3 8) (15 @5 8) (15 @7 8) (15 @9 8) (15 @11 8) (15 @13 8)]
            DLTC3[(4 @1 8) (4 @2 8) (4 @5 8) (5 @1 8) (5 @2 8) (5 @5 8) (12 @1 8) (12 @4 8) (13 @1 8) (13 @4 8) (14 @0 8) (14 @2 8) (14 @4 8) (15 @0 8) (15 @2 8) (15 @4 8)]
            """
        )

        ft_assembly = transform_assembly(vtt_assembly)

        assert (
            ft_assembly
            == dedent(
                """
                PUSH[] 15 14 15 15 31 4 31 5 31 12 31 13 47 4 47 5 47 14 47 15 79 12 79 13 79 14 79 15 95 4 95 5 16 31 12 31 13 31 14 31 15 63 4 63 5 63 12 63 13 63 14 63 15 79 12 79 13 95 12 95 13 95 14 95 15 111 4 111 5 127 4 127 5 127 14 127 15 159 12 159 13 159 14 159 15 175 4 175 5 191 14 191 15 223 12 223 13 223 14 223 15 239 4 239 5 36 15 12 15 13 31 12 31 13 79 4 79 5 79 12 79 13 95 12 95 13 143 4 143 5 143 12 143 13 159 12 159 13 191 4 191 5 191 14 191 15 223 12 223 13 223 14 223 15 255 4 255 5 255 12 255 13 255 14 255 15 30
                DELTAC1[]
                DELTAC2[]
                DELTAC3[]
                """
            ).strip()
        )

    def test_end_to_end(self, input_and_expected):
        vtt_assembly, expected = input_and_expected

        ft_assembly = transform_assembly(vtt_assembly)
        ft_program = make_ft_program(ft_assembly)
        generated = pformat_tti(ft_program)

        assert expected == generated


def test_TSIC_compile(tmp_path, original_shared_datadir):
    orig_ttf = original_shared_datadir / "NotoSans-MM-ASCII-VF.ttf"
    orig_ttx = original_shared_datadir / "NotoSans-MM-ASCII-VF.ttx"
    vtt_ttx = original_shared_datadir / "NotoSans-MM-ASCII-VF-VTT.ttx"
    vttLib_tmp_ttf = tmp_path / "NotoSans-MM-ASCII-VF.ttf"
    vtt_tmp_ttf = tmp_path / "NotoSans-MM-ASCII-VF-VTT.ttf"

    # Font built by vttLib
    shutil.copyfile(orig_ttf, vttLib_tmp_ttf)
    vtt_merge_file(orig_ttx, vttLib_tmp_ttf)
    vtt_compile(vttLib_tmp_ttf, force_overwrite=True)

    # Font built by VTT
    shutil.copyfile(orig_ttf, vtt_tmp_ttf)
    vtt_merge_file(vtt_ttx, vtt_tmp_ttf, keep_cvar=True)

    # Make sure they're the same
    vttLib_font = TTFont(vttLib_tmp_ttf)
    vtt_font = TTFont(vtt_tmp_ttf)
    assert "cvar" in vttLib_font
    assert "cvar" in vtt_font
    assert vttLib_font["cvar"] == vtt_font["cvar"]
    assert "cvt " in vttLib_font
    assert "cvt " in vtt_font
    assert vttLib_font["cvt "] == vtt_font["cvt "]
