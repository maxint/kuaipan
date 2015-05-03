# coding: utf-8

"""
Local cache for FuseFS
"""

import os
import logging
import threading

from .node import FileNode
from .node import NodeTree
from .kuaipan import KuaiPan

log = logging.getLogger(__name__)


class MemoryCache():
    def __init__(self, raw):
        self.raw = raw


class FileCache():
    def __init__(self, node, cached_path):
        assert isinstance(node, FileNode)
        self.node = node
        self.cached_path = cached_path
        self.raw = None
        self.fh = None
        self.modified = False
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
        if not os.path.exists(self.cached_path) or os.path.getmtime(self.cached_path) < self.node.attribute.mtime:
            if len(self.data) != self.node.attribute.size:
                log.info(u'from net %s (size=%d -> %d)', self.node.path,
                         len(self.data), self.node.attribute.size)
                self.data = ''
                self.raw = kp.download(self.node.path).raw
        else:
            log.info(u'open cache %s, mtime(%s -> %s)', self.node.path,
                     os.path.getmtime(self.cached_path), self.node.attribute.mtime)
            self.fh = os.open(self.cached_path, flags)

    def create(self):
        assert self.raw is None
        self.modified = True

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
                self.modified = True
            elif len(self.data) != length:
                self.data = self.data[:length]
                self.modified = True

    def write(self, data, offset):
        with self.lock:
            self.modified = True
            if self.fh is not None:
                os.lseek(self.fh, offset, 0)
                return os.write(self.fh, data)
            else:
                self.data = self.data[:offset] + data
                return len(data)

    def flush(self):
        if self.fh is not None and self.modified:
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
                if self.fh is not None:
                    os.close(self.fh)
                    kp.upload(self.node.path, open(self.cached_path, 'rb'), True)
                else:
                    kp.upload(self.node.path, self.data, True)

                self.node.update_meta(kp)

                if self.raw:
                    self.raw.close()

            if not os.path.exists(self.cached_path) or self.modified:
                if self.fh is None and (self.modified or self.raw is None):
                    # only save cache file when downloaded data is completed or modified
                    log.info(u'writing %s to cache', self.node.path)
                    with open(self.cached_path, 'wb') as f:
                        f.write(self.data)
                if os.path.exists(self.cached_path):
                    attribute = self.node.attribute
                    os.utime(self.cached_path, (attribute.mtime, attribute.mtime))
            self.modified = False


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
        log.debug('remove files elder than %d days', passed_day)
        for name in os.listdir(self.pool_dir):
            path = os.path.join(self.pool_dir, name)
            if os.path.getatime(path) < time_threshold:
                log.debug('remove old cache file %s', path)
                os.remove(path)

    def _get_cached_file(self, path):
        import hashlib
        m = hashlib.md5()
        m.update(path.encode('utf-8'))
        return os.path.join(self.pool_dir, m.hexdigest())

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
            c = FileCache(node, self._get_cached_file(path))
            c.open(self.kp, flags)
            self.data[path] = c

        c.ref_count += 1
        return c

    def create(self, path):
        if path in self.data:
            c = self.get(path)
        else:
            node = self.tree.create(path, False)
            c = FileCache(node, self._get_cached_file(path))
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
        old_cache_path = self._get_cached_file(old)
        if os.path.isfile(old_cache_path):
            new_cache_path = self._get_cached_file(new)
            os.rename(old_cache_path, new_cache_path)
