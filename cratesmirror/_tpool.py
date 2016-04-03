#!/usr/bin/python -O
# -*- coding: utf-8 -*-
"""
See also 'https://hg.python.org/cpython/file/3.5/Lib/concurrent/futures/thread.py'
         'https://hg.python.org/cpython/file/3.5/Lib/concurrent/futures/_base.py'
"""

from __future__ import print_function, unicode_literals
import atexit
import weakref
import threading
import traceback
from multiprocessing import cpu_count

try:
    import queue
except ImportError:
    import Queue as queue

_threads_queues = weakref.WeakKeyDictionary()

_shutdown = False

def _python_exit():
    global _shutdown
    _shutdown = True
    items = list(_threads_queues.items())
    for t, q in items:
        q.put(None)
    for t, q in items:
        t.join()

atexit.register(_python_exit)

def _worker(executor_reference, work_queue):
    try:
        while True:
            item = work_queue.get(block=True)
            if item is not None:
                item.run()
                del item
                continue

            executor = executor_reference()
            # Exit if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns the worker has been collected OR
            #   - The executor that owns the worker has been shutdown.
            if _shutdown or executor is None or executor._shutdown:
                # Notice other workers
                work_queue.put(None)
                return
            del executor
    except Exception:
        traceback.print_exc()

class _WorkItem(object):
    def __init__(self, fn, args, kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()

class ThreadPoolExecutor(object):

    def __init__(self, max_workers=None):

        if max_workers is None:
            max_workers = (cpu_count() or 1) * 5
        if max_workers < 0:
            raise ValueError("max_workers must be greater than 0")

        self._max_workers = max_workers
        self._threads = set()
        self._work_queue = queue.Queue()
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

    def map(self, fn, *iterables):

        for args in zip(*iterables):
            self.submit(fn, *args)

    def submit(self, fn, *args, **kwargs):

        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')

            w = _WorkItem(fn, args, kwargs)

            self._work_queue.put(w)
            self._adjust_thread_count()

    def _adjust_thread_count(self):
        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        def weakref_cb(_, q=self._work_queue):
            q.put(None)
        if len(self._threads) < self._max_workers:
            t = threading.Thread(target=_worker,
                                 args=(weakref.ref(self, weakref_cb),
                                       self._work_queue))
            t.daemon = True
            t.start()
            self._threads.add(t)
            _threads_queues[t] = self._work_queue

    def shutdown(self, wait=True):

        with self._shutdown_lock:
            self._shutdown = True
            self._work_queue.put(None)
        if wait:
            for t in self._threads:
                t.join()

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.shutdown(wait=True)
        return False

