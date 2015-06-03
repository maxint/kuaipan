# coding: utf-8

"""
Local cache for FuseFS
"""

import os
import logging
import threading
import time
import shutil

from .node import FileNode
from .node import NodeTree
from .kuaipan import KuaiPan

log = logging.getLogger(__name__)


class MemoryCache():
    def __init__(self, raw):
        self.raw = raw


class FileCache():
    def __init__(self, node, cache_path):
        assert isinstance(node, FileNode)
        self.node = node
        self.cache_path = cache_path
        self.raw = None
        self.fh = None
        self.modified = 0
        self.lock = threading.Lock()
        self.data = ''
        # reference count is needed, as file may be opened more than once.
        self.ref_count = 0

    def open(self, kp, flags):
        """
        :type kp: KuaiPan
        """
        assert self.raw is None
        log.info(u'opening %s (refcount=%d)', self.node.path, self.ref_count)
        cache_mtime = os.path.getmtime(self.cache_path) if os.path.exists(self.cache_path) else 0
        if cache_mtime < self.node.attribute.mtime:
            if len(self.data) != self.node.attribute.size:
                log.info(u'from net %s (size=%d -> %d)', self.node.path,
                         len(self.data), self.node.attribute.size)
                self.data = ''
                self.raw = kp.download(self.node.path).raw
        else:
            if cache_mtime > self.node.attribute.mtime:
                self.modified = 2  # previous not-uploaded data
            log.info(u'open cache %s, mtime(%s -> %s)', self.node.path,
                     os.path.getmtime(self.cache_path), self.node.attribute.mtime)
            self.fh = os.open(self.cache_path, flags)

    def create(self):
        assert self.raw is None
        self.modified = 1

    def read(self, size, offset):
        with self.lock:
            if self.fh is not None:
                os.lseek(self.fh, offset, 0)
                return os.read(self.fh, size)
            elif self.raw and len(self.data) < size + offset:
                total = size + offset
                read_size = total - len(self.data)
                if read_size > 0:
                    self.data += self.raw.read(read_size)
                    if not self.raw.readable() or len(self.data) == self.node.attribute.size:
                        # complete download
                        self.raw.close()
                        self.raw = None

            return self.data[offset:offset+size]

    def truncate(self, length):
        with self.lock:
            if self.fh is not None:
                os.ftruncate(self.fh, length)
                self.modified = 1
            elif len(self.data) != length:
                self.data = self.data[:length]
                self.modified = 1

    def write(self, data, offset):
        with self.lock:
            self.modified = 1
            if self.fh is not None:
                os.lseek(self.fh, offset, 0)
                return os.write(self.fh, data)
            else:
                if self.raw:
                    self.raw.close()
                    self.raw = None
                self.data = self.data[:offset] + data
                return len(data)

    def flush(self):
        if self.fh is not None and self.modified == 1:
            os.fsync(self.fh)

    def close(self, kp):
        """
        :type kp: KuaiPan
        """
        log.info('closing %s', self.node.path)
        with self.lock:
            # ignore temporary files
            name = os.path.basename(self.node.path)
            if name.startswith('.~') or name.startswith('~'):
                return

            if self.modified:
                # TODO: upload in background pool
                log.info("upload: %s", self.node.path)
                if self.fh is not None or self.modified == 2:
                    os.close(self.fh)
                    kp.upload(self.node.path, open(self.cache_path, 'rb'), True)
                else:
                    kp.upload(self.node.path, self.data, True)

                self.node.update_meta(kp)

            if self.raw:
                self.raw.close()

            if not os.path.exists(self.cache_path) or self.modified:
                if self.fh is None and (self.modified or self.raw is None):
                    # only save cache file when downloaded data is completed or modified
                    log.info(u'writing %s to cache', self.node.path)
                    cache_dir = os.path.dirname(self.cache_path)
                    if not os.path.exists(cache_dir):
                        os.makedirs(cache_dir)
                    with open(self.cache_path, 'wb') as f:
                        f.write(self.data)
                if os.path.exists(self.cache_path):
                    attribute = self.node.attribute
                    os.utime(self.cache_path, (time.time(), attribute.mtime))
            self.modified = 0


class CachePool():
    def __init__(self, tree, pool_dir):
        assert isinstance(tree, NodeTree)
        assert os.path.isdir(pool_dir)
        self.data = dict()
        self.tree = tree
        self.kp = tree.kp
        self.pool_dir = pool_dir
        self.clear_old_files()

    def clear_old_files(self, passed_day=30):
        """
        Clean cache files who's access time is before given days ago.
        """
        import time
        time_threshold = time.time() - passed_day * 60 * 60 * 24
        log.info('remove files elder than %d days', passed_day)

        def remove_if_old(name):
            path = os.path.join(root, name)
            if os.path.getatime(path) >= time_threshold:
                return True
            log.warn('remove old cache %s', path)
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
            return False

        for root, dirs, files in os.walk(self.pool_dir):
            dirs[:] = filter(remove_if_old, dirs)
            files[:] = filter(remove_if_old, files)

    def _get_cache_path(self, path):
        return self.pool_dir + path

    def get(self, path):
        """
        :rtype: FileCache
        """
        assert path in self.data
        return self.data[path]

    def open(self, path, flags):
        if path in self.data:
            c = self.get(path)
        else:
            node = self.tree.get(path)
            c = FileCache(node, self._get_cache_path(path))
            c.open(self.kp, flags)
            self.data[path] = c

        c.ref_count += 1
        return c

    def create(self, path):
        if path in self.data:
            c = self.get(path)
        else:
            node = self.tree.create(path, False)
            c = FileCache(node, self._get_cache_path(path))
            c.create()
            self.data[path] = c

        c.ref_count += 1
        return c

    def close(self, path):
        c = self.get(path)
        c.ref_count -= 1
        if c.ref_count == 0:
            c = self.data.pop(path, None)
            c.close(self.kp)

    def move(self, old, new):
        old_cache_path = self._get_cache_path(old)
        if os.path.exists(old_cache_path):
            new_cache_path = self._get_cache_path(new)
            os.rename(old_cache_path, new_cache_path)
