# coding: utf-8

"""
Local cache for FuseFS
"""

import os
import logging
import threading
import time
import shutil

from .node import AbstractNode
from .node import NodeTree
from .kuaipan import KuaiPan

log = logging.getLogger(__name__)


class FileCache(object):
    """
    :type raw: io.RawIOBase
    :type node: AbstractNode
    """
    def __init__(self, node, cache_path):
        self.node = node
        self.cache_path = cache_path
        self.raw = None
        self.fh = None
        self.flags = None
        self.modified = 0
        self.rwlock = threading.Lock()
        self.ref_lock = threading.Lock()
        self.data = ''
        # reference count is needed, as file may be opened more than once.
        self.ref_count = 0

    def add_ref(self):
        with self.ref_lock:
            self.ref_count += 1

    def delete_ref(self):
        with self.ref_lock:
            self.ref_count -= 1

    @property
    def refcount(self):
        with self.ref_lock:
            return self.ref_count

    def open(self, kp, flags):
        """
        :type kp: KuaiPan
        """
        with self.rwlock:
            assert self.raw is None
            log.info(u'opening %s (refcount=%d)', self.node.path, self.ref_count)
            self.flags = flags
            cache_mtime = os.path.getmtime(self.cache_path) if os.path.exists(self.cache_path) else 0
            if cache_mtime < self.node.attribute.mtime and len(self.data) != self.node.attribute.size:
                log.info(u'from net %s (size=%d -> %d)', self.node.path,
                         len(self.data), self.node.attribute.size)
                self.data = ''
                self.raw = kp.download(self.node.path).raw
            else:
                if cache_mtime > self.node.attribute.mtime:
                    self.modified = 2  # previous not-uploaded data
                log.info(u'open cache %s, mtime(%s -> %s)', self.node.path,
                         os.path.getmtime(self.cache_path), self.node.attribute.mtime)
                self._open_cache()

    def reopen(self, flags):
        with self.rwlock:
            self.flags = flags

    def create(self):
        with self.rwlock:
            assert self.raw is None
            log.info(u'creating %s (refcount=%d)', self.node.path, self.ref_count)
            self.modified = 1
            self.fh = os.open(self.cache_path, os.O_CREAT | os.O_RDWR)

    def read(self, size, offset):
        with self.rwlock:
            if self.fh is None:
                total = size + offset
                if len(self.data) < total:
                    if self._download(total - len(self.data)):
                        self._open_cache()
            if self.fh is not None:
                os.lseek(self.fh, offset, 0)
                return os.read(self.fh, size)
            else:
                return self.data[offset:(size + offset)]

    def truncate(self, length):
        with self.rwlock:
            if self.fh is not None:
                os.ftruncate(self.fh, length)
                self.modified = 1
            elif len(self.data) != length:
                self.data = self.data[:length]
                self.modified = 1

    def write(self, data, offset):
        with self.rwlock:
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
        if self.fh is not None and self.modified:
            os.fsync(self.fh)

    @property
    def completed(self):
        with self.rwlock:
            if self.fh is not None:
                return True
            elif self.modified:
                return True
            elif self.node.attribute.size == len(self.data):
                return True
            elif self.raw is None:
                return True

    @property
    def ignored(self):
        # ignore temporary files
        name = os.path.basename(self.node.path)
        return name.startswith('.~') or name.startswith('~')

    def close(self):
        log.info(u'closing %s', self.node.path)
        with self.rwlock:
            if self.ignored:
                log.warn(u'ignore %s', self.node.path)
                return True

            if self.fh:
                os.close(self.fh)

            if self.modified == 1 and self.fh is None:
                self._write_cache()

            self.fh = None

    def _open_cache(self):
        self.fh = os.open(self.cache_path, self.flags)
        self.data = ''

    def _download(self, size):
        """Return True if completed"""
        assert self.raw is not None
        self.data += self.raw.read(size)
        if self.raw.readable() and len(self.data) < self.node.attribute.size:
            return False

        assert len(self.data) == self.node.attribute.size
        log.debug(u'complete download: %s (%d)', self.node.path, len(self.data))
        self.raw.close()
        self.raw = None
        self._write_cache()
        self._update_cache_utime()

        return True

    def download(self, size):
        with self.rwlock:
            assert self.modified == 0
            return self.raw is None or self._download(size)

    def _upload(self, kp):
        """:type kp: KuaiPan"""
        log.info(u"upload: %s", self.node.path)
        if self.fh is not None:
            os.close(self.fh)
            kp.upload(self.node.path, open(self.cache_path, 'rb'), True)
        else:
            kp.upload(self.node.path, self.data, True)

        self.node.update_meta(kp)
        self._update_cache_utime()

    def upload(self, kp):
        """:type kp: KuaiPan"""
        with self.rwlock:
            if self.modified:
                self._upload(kp)
                self.modified = 0

    def _write_cache(self):
        log.info(u'writing %s to cache', self.node.path)
        cache_dir = os.path.dirname(self.cache_path)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        with open(self.cache_path, 'wb') as f:
            f.write(self.data)

    def _update_cache_utime(self):
        if os.path.exists(self.cache_path):
            log.debug(u'update cach utime: %s', self.cache_path)
            attribute = self.node.attribute
            os.utime(self.cache_path, (time.time(), attribute.mtime))


class CachePool(object):
    def __init__(self, tree, pool_dir):
        """
        :type tree: NodeTree
        :return:
        """
        assert os.path.isdir(pool_dir)
        self.data = dict()
        self.tree = tree
        self.kp = tree.kp
        self.pool_dir = pool_dir
        self.clear_old_files()

    def _download_item(self, c):
        """:type c: FileCache"""
        if c.refcount != 0:
            return False

        if not c.download(1024):
            return True

        if c.refcount == 0:
            self.data.pop(c.node.path)

        return False

    def _upload_item(self, c):
        """:type c: FileCache"""
        time.sleep(1)
        if c.refcount != 0:
            return False

        c.upload(self.kp)

        if c.refcount == 0:
            self.data.pop(c.node.path)

        return True

    def clear_old_files(self, passed_day=30):
        """
        Clean cache files who's access time is before given days ago.
        """
        import time
        time_threshold = time.time() - passed_day * 60 * 60 * 24
        log.info(u'remove files elder than %d days', passed_day)

        def remove_if_old(name):
            path = os.path.join(root, name)
            if os.path.getatime(path) >= time_threshold:
                return True
            log.warn(u'remove old cache %s', path)
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
            c.reopen(flags)
        else:
            node = self.tree.get(path)
            c = FileCache(node, self._get_cache_path(path))
            c.open(self.kp, flags)
            self.data[path] = c

        c.add_ref()
        return c

    def create(self, path):
        if path in self.data:
            c = self.get(path)
        else:
            node = self.tree.create(path, False)
            c = FileCache(node, self._get_cache_path(path))
            self.data[path] = c

        c.add_ref()
        c.create()
        return c

    def close(self, path):
        c = self.get(path)
        c.delete_ref()
        if c.refcount == 0:
            if c.close():
                self.data.pop(path)
            elif c.modified:
                log.debug(u'running upload thread: %s', path)
                QueueThread(self._upload_item, c)
            elif not c.completed:
                log.debug(u'running download thread: %s', path)
                QueueThread(self._download_item, c)
            else:
                log.debug(u'pop file cache: %s', path)
                self.data.pop(path)

    def move(self, old, new):
        old_cache_path = self._get_cache_path(old)
        if os.path.exists(old_cache_path):
            new_cache_path = self._get_cache_path(new)
            os.rename(old_cache_path, new_cache_path)


class QueueThread(threading.Thread):
    def __init__(self, run_func, item):
        super(QueueThread, self).__init__()
        self.run_func = run_func
        self.item = item

    def run(self):
        while True:
            if not self.run_func(self.item):
                break
