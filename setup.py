#!/usr/bin/python -O
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import re

PACKAGE = "cratesmirror"
NAME = "cratesmirror"
DESCRIPTION = "Download all crates on https://crates.io"
AUTHOR = "Knight"
LICENSE="MIT"
AUTHOR_EMAIL = "anonymousknight96@gmail.com"
URL = "https://github.com/ustclug/LUG-crates_mirror"

with open('README.rst', 'r') as f:
    readme = f.read()

with open('cratesmirror/__init__.py', 'r') as fd:
    VERSION = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fd.read(), re.MULTILINE).group(1)

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
        "Environment :: Console",
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
    install_requires = [
        'requests>=2.9.1',
        'GitPython>=1.0.2'
    ],
    zip_safe=False,
    entry_points={
        'console_scripts':[
            'cratesmirror = cratesmirror.__main__:main'
        ]
    }
)
