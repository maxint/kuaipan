# coding: utf-8

"""
Fuse file system for kuaipan.cn

Code inspired from https://github.com/wusuopu/kuaipan-linux
"""

import os
import errno
import fuse
import logging

import cache
from .node import NodeTree

log = logging.getLogger(__name__)


class LoggingMixIn:
    def __call__(self, op, path, *args):
        log.debug('-> %s: %s (%s)', op, path, ','.join(map(str, args)))
        ret = '[Unhandled Exception]'
        try:
            ret = getattr(self, op)(path, *args)
            return ret
        except OSError, e:
            ret = str(e)
            raise
        finally:
            def cap_string(s, l):
                return s if len(s) < l else s[0:l - 3] + '...'

            if isinstance(ret, str) and len(ret) > 1024:
                msg = cap_string(repr(ret[:10]), 10)
            else:
                msg = repr(ret)
            log.debug('<- %s: %s %s', op, path, msg)


class KuaipanFuse(LoggingMixIn, fuse.Operations):
    def __init__(self, kp, pool_dir):
        self.kp = kp
        self.caches = cache.CachePool(pool_dir)
        self.pool_dir = pool_dir
        self.tree = NodeTree(kp, pool_dir)

    def get_path(self, path):
        return os.path.join(self.pool_dir, path)

    # ----------------------------------------------------

    def access(self, path, amode):
        return 0

    def getattr(self, path, fh=None):
        node = self.tree.get(path)
        if not node:
            raise fuse.FuseOSError(errno.ENOENT)
        return node.attribute.get()

    def readdir(self, path, fh):
        node = self.tree.get(path)
        if not node:
            raise fuse.FuseOSError(errno.ENOENT)
        return node.names()

    def rename(self, old, new):
        self.kp.move(old, new)
        self.tree.move(old, new)

    def mkdir(self, path, mode=0644):
        self.kp.mkdir(path)
        self.tree.create(path, True)

    def rmdir(self, path):
        self.kp.delete(path)
        self.tree.remove(path)

    def unlink(self, path):
        self.rmdir(path)
        self.caches.remove(path)

    def open(self, path, flags):
        if path not in self.caches:
            st_size = self.getattr(path)['st_size']
            self.caches.add(path, self.kp.download(path), st_size)
        return 0

    def release(self, path, fh):
        return 0

    def read(self, path, size, offset, fh):
        return self.caches[path].read(size, offset)

    def truncate(self, path, length, fh=None):
        it = self.caches[path]
        it.truncate(length)
        node = self.tree.get(path)
        node.attribute.set_size(length)

    def write(self, path, data, offset, fh):
        it = self.caches[path]
        it.write(data, offset)
        node = self.tree.get(path)
        node.attribute.set_size(offset + len(data))
        return len(data)

    def flush(self, path, fh):
        self.caches[path].flush(path, self.kp)
        node = self.tree.get(path)
        node.attribute.update()
        return 0

    def create(self, path, mode=0644, fi=None):
        self.caches.add(path)
        self.tree.create(path, False)
        name = os.path.basename(path)
        if name.startswith('.~') or name.startswith('~'):
            return 0
        self.kp.upload(path, '', True)
        return 0