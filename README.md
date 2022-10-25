[![Build Status](https://travis-ci.org/daltonmaag/vttLib.svg?branch=master)](https://travis-ci.org/daltonmaag/vttLib)

# vttLib

A library to

1. Extract VTT hinting data from a OpenType font prepared with [Microsoft Visual TrueType (VTT)](https://docs.microsoft.com/en-us/typography/tools/vtt/) and store it in a [FontTools](https://github.com/fonttools/fonttools/) TTX dump
2. Merge it back from a TTX dump into an OpenType font and
3. Compile the data inside to font to ship it (turn `TSI*` tables into `fpgm`, etc.).

The primary use case is version control of hinting data of fonts.

## Installation and Usage

Installation requires a Python 3.7+ interpreter.

Install in a virtual environment with:

```bash
$ pip install vttLib
$ python -m vttLib --help
```

# Making a Release

This is currently not automated.

1. Tag a new version
2. `python3 setup.py bdist_wheel`
3. Manually transfer `dist/*.whl` to internal package repository.
