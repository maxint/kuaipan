# coding: utf-8

"""
Local cache for FuseFS
"""

import os
import logging
import threading

from .node import FileNode
from .node import NodeTree

log = logging.getLogger(__name__)


class FileCache():
    def __init__(self, node, r=None):
        assert isinstance(node, FileNode)
        self.node = node
        self.raw = r.raw if r else None
        self.data = bytes()
        self.total = node.attribute.size
        self.modified = False
        self.lock = threading.Lock() if r else None

    def readable(self):
        return self.raw and self.raw.readable()

    def size(self):
        return len(self.data)

    def _read(self, total):
        bufsz = self.size()
        if bufsz < total and self.readable():
            try:
                self.data += self.raw.read(total - bufsz)
            except (StopIteration, ValueError):
                self.raw.close()
                self.raw = None
                self.lock = None

    def read(self, size, offset):
        total = size + offset
        # add multiple thread protection for reading
        if self.lock:
            with self.lock:
                self._read(total)
        fsize = min(total, self.size())
        return self.data[offset:fsize]

    def truncate(self, length):
        if len(self.data) != length:
            self.data = self.data[:length]
            self.modified = True
            self.node.attribute.set_size(length)

    def write(self, data, offset):
        self.data = self.data[:offset] + data
        self.modified = True
        self.node.attribute.set_size(len(self.data))
        return len(data)

    def flush(self, path, kp):
        if self.modified:
            log.debug("upload: %s", path)
            kp.upload(path, self.data, True)
            self.modified = False


class CachePool():
    def __init__(self, tree, pool_dir):
        assert isinstance(tree, NodeTree)
        assert os.path.isdir(pool_dir)
        self.data = dict()
        self.tree = tree
        self.kp = tree.kp
        self.pool_dir = pool_dir

    def __getitem__(self, path):
        c = self.data[path]
        assert isinstance(c, FileCache)
        return c

    def __contains__(self, path):
        return path in self.data

    def get(self, path):
        return self.data.get(path)

    def open(self, path):
        if path in self.data:
            return self.data[path]

        node = self.tree.get(path)
        r = self.kp.download(path)
        c = FileCache(node, r)
        self.data[path] = c

        return c

    def create(self, path):
        if path in self.data:
            return self.data[path]

        node = self.tree.create(path, False)
        name = os.path.basename(path)
        if not name.startswith('.~') and not name.startswith('~'):
            # TODO: remove it?
            self.kp.upload(path, '', True)

        c = FileCache(node)
        self.data[path] = c

        return c

    def flush(self, path):
        c = self.data[path]
        assert isinstance(c, FileCache)
        c.flush(path, self.kp)
        c.node.attribute.update()

    def remove(self, path):
        self.data.pop(path, None)
