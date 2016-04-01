#!/usr/bin/python -O
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement, division

import os

def walk_git(gitdir):
    for root, dirs, files in os.walk(gitdir):
        if '.git' in dirs:
            dirs.remove('.git')
        for f in files:
            if f != 'config.json':
                yield os.path.join(root, f)

def gen_lines(fp, latest_only=False):
    with open(fp, 'r') as json_file:
        if latest_only:
            last_line = ''
            for line in json_file:
                last_line = line
            yield last_line
        else:
            for line in json_file:
                yield line

def foreach(f, *args):
    list(map(f, *args))

def producer(gitdir):
    for f in walk_git(gitdir):
        for line in gen_lines(f):
            pass

if __name__ == '__main__':
    d = '/home/knight/.cargo/registry/index/crates.mirrors.ustc.edu.cn-4496af6807a54617/'
    for i in walk_git(d):
        print(i)
