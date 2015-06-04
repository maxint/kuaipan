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

NOT_MODIFIED = 0
MODIFIED = 1
NOT_UPLOADED = 2


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
        self.modified = NOT_MODIFIED
        self.rwlock = threading.RLock()
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

    @property
    def is_opened(self):
        with self.rwlock:
            return self.raw is not None or self.fh is not None

    def open(self, kp, flags):
        """
        :type kp: KuaiPan
        """
        with self.rwlock:
            log.info(u'opening %s (refcount=%d)', self.node.path, self.refcount)
            self.flags = flags
            if self.is_opened:
                return

            cache_mtime = os.path.getmtime(self.cache_path) if os.path.exists(self.cache_path) else 0
            log.debug(u'modified time (%s -> %s): %s', cache_mtime, self.node.attribute.mtime, self.node.path)
            if cache_mtime < self.node.attribute.mtime and len(self.data) != self.node.attribute.size:
                log.info(u'from net (size=%d -> %d): %s', len(self.data), self.node.attribute.size, self.node.path)
                self.data = ''
                self.raw = kp.download(self.node.path).raw
            else:
                if cache_mtime > self.node.attribute.mtime:
                    self.modified = NOT_UPLOADED  # previous not-uploaded _cache_dict
                log.info(u'open cache: %s', self.node.path)
                self._open_cache()

    def create(self):
        with self.rwlock:
            assert self.raw is None
            log.info(u'creating %s (refcount=%d)', self.node.path, self.refcount)
            self.modified = MODIFIED
            self.fh = os.open(self.cache_path, os.O_CREAT | os.O_RDWR)

    def read(self, size, offset):
        with self.rwlock:
            if self.fh is None:
                total = size + offset
                if len(self.data) < total:
                    if self.download(total - len(self.data)):
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
                self.modified = MODIFIED
            elif len(self.data) != length:
                self.data = self.data[:length]
                self.modified = MODIFIED

    def write(self, data, offset):
        with self.rwlock:
            self.modified = MODIFIED
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
        if self.fh is not None and self.modified != NOT_MODIFIED:
            os.fsync(self.fh)

    @property
    def completed(self):
        with self.rwlock:
            if self.fh is not None:
                return True
            elif self.modified != NOT_MODIFIED:
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

            if self.modified == MODIFIED and self.fh is None:
                self._write_cache()

            self.fh = None

    def _open_cache(self):
        self.fh = os.open(self.cache_path, self.flags)
        self.data = ''

    def download(self, size):
        with self.rwlock:
            assert self.modified == NOT_MODIFIED
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

    def upload(self, kp):
        """:type kp: KuaiPan"""
        with self.rwlock:
            if self.modified == NOT_MODIFIED:
                return

            """:type kp: KuaiPan"""
            log.info(u"upload: %s", self.node.path)
            if self.fh is not None:
                os.close(self.fh)
                kp.upload(self.node.path, open(self.cache_path, 'rb'), True)
            else:
                kp.upload(self.node.path, self.data, True)

            self.node.update_meta(kp)
            self._update_cache_utime()
            self.modified = NOT_MODIFIED

    def _write_cache(self):
        log.info(u'writing to cache: %s', self.node.path)
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
        self._cache_dict = dict()
        self.tree = tree
        self.kp = tree.kp
        self.pool_dir = pool_dir
        self._clear_old_files()

    def _clear_old_files(self, passed_day=30):
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

    def _add(self, path):
        log.debug(u'add cache path: %s', path)
        if path in self._cache_dict:
            c = self.get(path)
        else:
            node = self.tree.get(path)
            c = FileCache(node, self._get_cache_path(path))
            self._cache_dict[path] = c
        c.add_ref()
        return  c

    def _remove(self, c, delete=True):
        """:type c: FileCache"""
        c.delete_ref()
        if delete:
            c = self._remove_if_no_ref(c)
        return c

    def _remove_if_no_ref(self, c):
        """:type c: FileCache"""
        log.debug(u'remove cache path: %s (refcount=%d)', c.node.path, c.refcount)
        if c.refcount == 0:
            c = self._cache_dict.pop(c.node.path)
        return c

    def _download_item(self, c):
        """:type c: FileCache"""
        while True:
            if c.refcount > 0:
                return
            if c.download(1024):
                break

        self._remove_if_no_ref(c)

    def _upload_item(self, c):
        """:type c: FileCache"""
        time.sleep(0.5)

        if c.refcount > 0:
            return
        c.upload(self.kp)

        self._remove_if_no_ref(c)

    def contains(self, path):
        return path in self._cache_dict

    def get(self, path):
        """:rtype: FileCache"""
        return self._cache_dict[path]

    def open(self, path, flags):
        c = self._add(path)
        try:
            c.open(self.kp, flags)
        except:
            log.warn(u'open failed: %s (refcount=%d)', path, c.refcount)
            self._remove(c)
            raise
        return c

    def create(self, path):
        c = self._add(path)
        try:
            c.create()
        except:
            log.warn(u'create failed: %s (refcount=%d)', path, c.refcount)
            self._remove(c)
            raise
        return c

    def close(self, path):
        c = self._remove(self.get(path), delete=False)
        if c.refcount == 0:
            if c.close():
                self._cache_dict.pop(path)
            elif c.modified:
                log.debug(u'running upload thread: %s', path)
                HelperThread(self._upload_item, c).start()
            elif not c.completed:
                log.debug(u'running download thread: %s', path)
                HelperThread(self._download_item, c).start()
            else:
                log.debug(u'pop file cache: %s', path)
                self._cache_dict.pop(path)

    def move(self, old, new):
        old_cache_path = self._get_cache_path(old)
        if os.path.exists(old_cache_path):
            new_cache_path = self._get_cache_path(new)
            os.rename(old_cache_path, new_cache_path)


class HelperThread(threading.Thread):
    def __init__(self, run_func, *args):
        super(HelperThread, self).__init__()
        self.run_func = run_func
        self.args = args

    def run(self):
        try:
            self.run_func(*self.args)
        except:
            log.exception('Exception raised in HelperThread')
            raise
