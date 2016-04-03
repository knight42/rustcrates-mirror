#!/usr/bin/python -O
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement, division

import os
try:
    import queue
except ImportError:
    import Queue as queue
import time

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


class TaskQueue(queue.Queue):

    def __iter__(self):

        while 1:
            try:
                item = self.get_nowait()
            except queue.Empty:
                time.sleep(2)
            else:
                if item is None:
                    break
                yield item

