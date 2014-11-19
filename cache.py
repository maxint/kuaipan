#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 maxint <NOT_SPAM_lnychina@gmail.com>
# Distributed under terms of the MIT license.

"""
Local cache for FuseFS
"""
import threading

import logging
log = logging.getLogger('kpfuse')


class FileCache():
    def __init__(self, r=None, tsize=0):
        self.raw = r.raw if r else None
        self.data = bytes()
        self.tsize = tsize
        self.modified = False
        self.lock = threading.Lock() if r else None

    def readable(self):
        return self.raw and self.raw.readable()

    def read(self, size, offset):
        total = size + offset
        # add multiple thread protection for reading
        with self.lock:
            bufsz = len(self.data)
            if bufsz < total and self.readable():
                try:
                    self.data += self.raw.read(total - bufsz)
                except (StopIteration, ValueError):
                    self.raw.close()
                    self.raw = None
                bufsz = len(self.data)
        fsize = min(total, bufsz)
        return self.data[offset:fsize]

    def truncate(self, length):
        if len(self.data) != length:
            self.data = self.data[:length]
            self.modified = True

    def write(self, data, offset):
        self.data = self.data[:offset] + data
        self.modified = True

    def flush(self, path, kp):
        if self.modified:
            log.debug("upload: %s", path)
            kp.upload(path, self.data, True)
            self.modified = False


class CachePool():
    def __init__(self, pooldir=None):
        self.data = dict()
        self.pooldir = pooldir

    def get(self, path):
        return self.data.get(path)

    def __getitem__(self, path):
        return self.get(path)

    def add(self, path, r=None, tsize=0):
        if path not in self.data:
            c = FileCache(r, tsize)
            self.data[path] = c
            return c
        else:
            return self.get(path)

    def remove(self, path):
        self.data.pop(path, None)

    def __contains__(self, path):
        return path in self.data
