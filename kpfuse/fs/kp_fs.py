#!/usr/bin/env python
# coding: utf-8

import os
import logging
import threading
import fs.base

from .kp_file import CachePool
from .kp_node import NodeTree
from .kp_node import FileNode
from .kp_node import DirNode


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
            finally:
                if isinstance(ret, str) or isinstance(ret, bytes) or isinstance(ret, unicode):
                    msg = u"{}...({})".format(repr(ret[:10]), len(ret))
                else:
                    msg = repr(ret)
                self.log.debug(u"<- %s: %s %s", op, path, msg)
        except:
            self.log.exception('__call__ exception')
            raise


class KuaipanFS(fs.base.FS, LoggingMixIn):
    """
    :type kp: kuaipan.KuaiPan
    """
    def __init__(self, kp, profile_dir, thread_synchronize=True):
        fs.base.FS.__init__(self, thread_synchronize)
        self.kp = kp
        self.tree = NodeTree(kp)
        self.profile_dir = profile_dir
        self.cache_dir = os.path.join(profile_dir, 'object')
        self.fd = 0
        self.fd_map = dict()
        self.rwlock = threading.Lock()
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.caches = CachePool(self.tree, self.cache_dir)

    def __del__(self):
        with self.rwlock:
            del self.caches     # Invoke the destructor

    def _get_fd(self, c):
        if len(self.fd_map) != 0:
            self.fd += 1
        self.fd_map[self.fd] = c
        return self.fd

    # ----------------------------------------------------

    def open(self, path, mode='r', buffering=-1, encoding=None, errors=None,
             newline=None, line_buffering=False, **kwargs):
        # Opens a file for read/writing
        pass

    def isfile(self, path):
        # Check whether the path exists and is a file
        return isinstance(self.tree.get(path), FileNode)

    def isdir(self, path):
        # Check whether a path exists and is a directory
        return isinstance(self.tree.get(path), DirNode)

    def listdir(self, path='./', wildcard=None, full=False, absolute=False, dirs_only=False, files_only=False):
        # List the contents of a directory
        pass

    def makedir(self, path, recursive=False, allow_recreate=False):
        # Create a new directory
        with self.rwlock:
            self.kp.mkdir(path)
            self.tree.create(path, True)

    def remove(self, path):
        # Remove an existing file
        with self.rwlock:
            # TODO: force delete not-uploaded new file
            self.kp.delete(path, force=True)
            self.tree.remove(path)

    def removedir(self, path, recursive=False, force=False):
        # Remove an existing directory
        with self.rwlock:
            # TODO: force delete not-uploaded new file
            self.kp.delete(path, force=force)
            self.tree.remove(path)

    def rename(self, src, dst):
        # Atomically rename a file or directory
        with self.rwlock:
            self.kp.move(src, dst)
            self.tree.move(src, dst)
            self.caches.move(src, dst)

    def getinfo(self, path):
        # Return information about the path e.g. size, modified_time
        pass
