#!/usr/bin/env python3
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
    """Get the package version."""
    here = Path(__file__).resolve()
    version_file = here / "src" / "fabric_cnc" / "__init__.py"
    with open(version_file, mode="r") as f:
        file_lines = f.readlines()
    for line in file_lines:
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


extra_deps = {
    "dev": [
        "pytest>=7.0",
        "pytest-cov",
        "black",
        "isort",
        "mypy",
        "ruff",
    ],
    "plotting": [
        "ipywidgets",
        "matplotlib",
        "seaborn",
        "plotly",
    ]
}

setup(
    name="fabric_cnc",
    version=get_version(),
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.11",
    install_requires=["numpy", "pandas"],
    extras_require=extra_deps,
    author="Peter Briggs",
    author_email="pacbriggs@gmail.com",
)
