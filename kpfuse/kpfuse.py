# coding: utf-8

"""
Fuse file system for kuaipan.cn

Code inspired from https://github.com/wusuopu/kuaipan-linux
"""

import os
import errno
import fuse
import logging
import threading

import cache
from .node import NodeTree

log = logging.getLogger(__name__)


class LoggingMixIn:
    log = logging.getLogger('kpfuse.log-mixin')

    def __call__(self, op, path, *args):
        try:
            log.debug(u'-> %s: %s (%s) [%s]', op, path,
                      ','.join(map(str, args)),
                      threading.current_thread().name)
            ret = '[Unhandled Exception]'
            try:
                ret = getattr(self, op)(path, *args)
                return ret
            except OSError, e:
                ret = str(e)
                raise
                # raise fuse.FuseOSError(errno.EFAULT)
            finally:
                def cap_string(s, l):
                    return s if len(s) < l else s[0:l - 3] + '... ({})'.format(len(s))

                if (isinstance(ret, str) or isinstance(ret, unicode) or isinstance(ret, bytes)) and len(ret) > 128:
                    msg = cap_string(repr(ret[:10]), 10)
                else:
                    msg = repr(ret)
                log.debug('<- %s: %s %s', op, path, msg)
        except fuse.FuseOSError, e:
            raise
        except:
            log.exception('__call__ exception')
            raise


class KuaipanFuse(LoggingMixIn, fuse.Operations):
    def __init__(self, kp, pool_dir):
        self.kp = kp
        self.tree = NodeTree(kp)
        cache_dir = os.path.join(pool_dir, 'object')
        self.fd = 0
        self.fd_map = dict()
        self.rwlock = threading.Lock()
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.caches = cache.CachePool(self.tree, cache_dir)

    def _get_fd(self, c):
        if len(self.fd_map) != 0:
            self.fd += 1
        self.fd_map[self.fd] = c
        return self.fd

    # ----------------------------------------------------

    def access(self, path, amode):
        # whether path is accessible?
        return 0

    def getattr(self, path, fh=None):
        # get attribute of file or directory
        node = self.tree.get(path)
        if not node:
            raise fuse.FuseOSError(errno.ENOENT)
        return node.attribute.get()

    def getxattr(self, path, name, position=0):
        return ''

    def readdir(self, path, fh):
        # return name list in directory
        node = self.tree.get(path)
        if not node:
            raise fuse.FuseOSError(errno.ENOENT)
        return ['.', '..'] + node.names()

    def rename(self, old, new):
        # rename file or directory
        with self.rwlock:
            self.kp.move(old, new)
            self.tree.move(old, new)
            self.caches.move(old, new)

    def mkdir(self, path, mode=0644):
        # create directory
        with self.rwlock:
            self.kp.mkdir(path)
            self.tree.create(path, True)

    def rmdir(self, path):
        # remove directory
        with self.rwlock:
            self.kp.delete(path)
            self.tree.remove(path)

    def unlink(self, path):
        # remove file or directory
        self.rmdir(path)

    def create(self, path, mode=0644, fi=None):
        # create file
        with self.rwlock:
            c = self.caches.create(path)
            return self._get_fd(c)

    def open(self, path, flags):
        # open file for reading or writing
        with self.rwlock:
            c = self.caches.open(path, flags)
            return self._get_fd(c)

    def release(self, path, fh):
        # close file
        with self.rwlock:
            self.caches.close(path)
            self.fd_map.pop(fh)
            return 0

    def read(self, path, size, offset, fh):
        # read data from file
        c = self.fd_map[fh]
        return c.read(size, offset)

    def write(self, path, data, offset, fh):
        # write date to file
        c = self.fd_map[fh]
        return c.write(data, offset)

    def truncate(self, path, length, fh=None):
        # truncate data in file
        with self.rwlock:
            c = self.caches.get(path) if fh is None else self.fd_map[fh]
            return c.truncate(length)

    def flush(self, path, fh):
        # flush file data to disk
        self.fd_map[fh].flush()
        return 0