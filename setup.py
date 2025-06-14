#!/usr/bin/env/ python3
# -*- coding: utf-8 -*-
"""
FILE: setup.py
FILE THEME: Setup file for fabric_cnc package.
PROJECT: fabric_cnc
ORIGINAL AUTHOR: pbriggs
DATE CREATED: 14 June 2025
"""

from pathlib import Path
from setuptools import setup, find_packages


def get_version():
    """Get the logging version for setup.py."""
    here = Path(__file__).resolve()
    version_file = here.parent / "fabric_cnc/__init__.py"
    with open(version_file, mode="r") as f:
        file_lines = f.readlines()
    for line in file_lines:
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


extra_deps = {"notebook_plotting": ["ipywidgets", "matplotlib", "seaborn", "plotly"]}
setup(
    name="fabric_cnc",
    version=get_version(),
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=["numpy" , "pandas"],
    extras_require=extra_deps,
    tests_require=["pytest"],
    author="Peter Briggs",
    author_email="pacbriggs@gmail.com",
)
