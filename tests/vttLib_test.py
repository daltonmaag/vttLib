import os
from textwrap import dedent

import pytest

from vttLib import make_ft_program, pformat_tti, transform_assembly

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

    def test_end_to_end(self, input_and_expected):
        vtt_assembly, expected = input_and_expected

        ft_assembly = transform_assembly(vtt_assembly)
        ft_program = make_ft_program(ft_assembly)
        generated = pformat_tti(ft_program)

        assert expected == generated
