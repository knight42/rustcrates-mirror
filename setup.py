#!/usr/bin/python -O
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

PACKAGE = "cratesmirror"
NAME = "cratesmirror"
DESCRIPTION = "Download all crates on https://crates.io"
AUTHOR = "Knight"
LICENSE="MIT"
AUTHOR_EMAIL = "anonymousknight96@gmail.com"
URL = "https://github.com/ustclug/LUG-crates_mirror"
VERSION = __import__(PACKAGE).__version__

with open('README.rst', 'r') as f:
    readme = f.read()

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
     long_description=readme,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license=LICENSE,
    url=URL,
    packages=find_packages(exclude=["tests.*", "tests"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    zip_safe=False,
)
