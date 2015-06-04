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


class LoggingMixIn(object):
    log = logging.getLogger('kpfuse.log-mixin')

    def __call__(self, op, path, *args):
        try:
            self.log.debug(u"-> %s: %s (%s) [%s]", op, path,
                           ','.join(map(str, args)),
                           threading.current_thread().name)
            ret = "[Unhandled Exception]"
            try:
                ret = getattr(self, op)(path, *args)
                return ret
            except OSError, e:
                ret = str(e)
                raise
                # raise fuse.FuseOSError(errno.EFAULT)
            finally:
                if isinstance(ret, str) or isinstance(ret, bytes) or isinstance(ret, unicode):
                    msg = "{}...({})".format(ret[:10].encode('utf-8'), len(ret))
                else:
                    msg = repr(ret)
                self.log.debug(u"<- %s: %s %s", op, path, msg)
        except fuse.FuseOSError:
            raise
        except:
            self.log.exception('__call__ exception')
            raise


class KuaipanFuseOperations(LoggingMixIn, fuse.Operations):
    """
    :type kp: kuaipan.KuaiPan
    """
    def __init__(self, kp, profile_dir):
        self.kp = kp
        self.tree = NodeTree(kp)
        self.profile_dir = profile_dir
        self.cache_dir = os.path.join(profile_dir, 'object')
        self.fd = 0
        self.fd_map = dict()
        self.rwlock = threading.Lock()
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.caches = cache.CachePool(self.tree, self.cache_dir)

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