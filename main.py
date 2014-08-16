#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2014 maxint <NOT_SPAM_lnychina@gmail.com>
#
# Distributed under terms of the MIT license.

"""
Fuse file system for kuaipan.cn

Code inspired from https://github.com/wusuopu/kuaipan-linux
"""
import kuaipan
import fuse
import stat
import sys
import time
import logging
import errno

log = logging.getLogger(__file__)


def log_to_stdout(log):
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(fmt)
    log.addHandler(ch)


def cap_string(s, l):
    return s if len(s) < l else s[0:l - 3] + '...'


def get_time(time_str):
    return time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M:%S"))


def create_stat(isdir, size=0, ctime=None, mtime=None):
    now = time.time()
    if ctime is None:
        ctime = now
    if mtime is None:
        mtime = now
    if isdir:
        return dict(st_mode=(stat.S_IFDIR | 0644), st_nlink=2,
                    st_ctime=ctime, st_mtime=mtime, st_atime=mtime)
    else:
        return dict(st_mode=(stat.S_IFREG | 0644), st_nlink=1,
                    st_size=size,
                    st_ctime=ctime, st_mtime=mtime, st_atime=mtime)


def create_stat2(meta):
    if meta.get('path') == '/':
        return create_stat(True)
    else:
        return create_stat(meta['type'] == 'folder',
                           meta.get('size', 0),
                           get_time(meta['create_time']),
                           get_time(meta['modify_time']))


class ContentCache():
    def __init__(self, r=None, tsize=0):
        self.raw = r
        self.data = bytes()
        self.tsize = tsize
        self.modified = False

    def read(self, size, offset):
        total = size + offset
        bufsz = len(self.data)
        if bufsz < total and self.raw.readable():
            try:
                self.data += self.raw.read(total - bufsz)
            except (StopIteration, ValueError):
                self.raw.close()
            bufsz = len(self.data)
        fsize = min(total, bufsz)
        return self.data[offset:fsize]

    def truncate(self, length):
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


class KuaipanFuse(fuse.LoggingMixIn, fuse.Operations):
    def __init__(self, kp):
        self.kp = kp
        self.data_caches = dict()
        self.tree = dict()
        self.build('/')

    def build(self, path, node=None):
        """
        {
            type: 'file' or 'folder'
            attrs: {
                st_mode:
                st_nlink:
                st_ctime:
                st_atime:
                st_mtime:
            }
            [dirs]: ['.', '..', ...]
            [files]: {
                'path': {
                    type:
                    attrs:
                    [dirs]:
                    [files]:
                }
            }
        }
        """
        if node is None:
            node = self.get_node(path)
        meta = self.kp.metadata(path)
        if meta is None:
            return

        node['attrs'] = create_stat2(meta)
        if meta.get('path') == '/' or meta['type'] == 'folder':
            node['type'] = 'folder'
            files = meta.get('files', [])
            if 'dirs' not in node:
                node['dirs'] = [x['name'] for x in files] + ['.', '..']
            if 'files' not in node:
                fnodes = dict()
                for x in files:
                    fnodes[x['name']] = dict(type=x['type'],
                                             attrs=create_stat2(x),
                                             )
                node['files'] = fnodes
        else:
            node['type'] = 'file'

        return node

    def get_node(self, path, dirs=False):
        if path == '/':
            return self.tree

        names = path.strip('/').split('/')
        node = self.tree
        cur_dir = '/'
        for name in names:
            if node.get('type') != 'folder':
                return

            if 'files' not in node:
                if self.build(cur_dir, node) is None:
                    return
            node = node.get('files').get(name)
            if node is None:
                return
            cur_dir += name + '/'

        if node.get('type') == 'folder' and 'dirs' not in node and dirs:
            self.build(path, node)
        return node

    def create_node(self, path, isdir):
        node = dict(type='folder' if isdir else 'file',
                    attrs=create_stat(isdir))
        return self.insert_node(path, node)

    def pop_node(self, path):
        adir, aname = os.path.split(path)
        pnode = self.get_node(adir)
        if pnode:
            pnode['dirs'].remove(aname)
            pnode['attrs']['st_mtime'] = time.time()
            return pnode['files'].pop(aname, None)

    def insert_node(self, path, node):
        adir, aname = os.path.split(path)
        pnode = self.get_node(adir)
        if pnode:
            pnode['files'][aname] = node
            pnode['dirs'].append(aname)
            pnode['attrs']['st_mtime'] = time.time()
        return node

    #----------------------------------------------------

    def access(self, path, amode):
        log.debug("access: %s, amode=%s", path, str(amode))
        return 0

    def getattr(self, path, fh=None):
        log.debug("getattr: %s, fh=%s", path, str(fh))
        node = self.get_node(path, False)
        if not node:
            log.debug("getattr: %s not exists!", path)
            raise fuse.FuseOSError(errno.ENOENT)
        return node['attrs']

    def readdir(self, path, fh):
        log.debug("readdir: %s, fh=%s", path, str(fh))
        return self.get_node(path, True)['dirs']

    def rename(self, old, new):
        log.debug("rename %s to %s", old, new)
        self.kp.move(old, new)
        # update
        node = self.pop_node(old)
        if node:
            self.insert_node(new, node)

    def mkdir(self, path, mode=0644):
        log.debug("mkdir: %s, mode=%d", path, mode)
        self.kp.mkdir(path)
        self.create_node(path, True)

    def rmdir(self, path):
        log.debug("rmdir: %s", path)
        self.kp.delete(path)
        self.pop_node(path)

    def unlink(self, path):
        log.debug("unlink: %s", path)
        self.rmdir(path)
        self.data_caches.pop(path)

    def open(self, path, flags):
        log.debug("open: %s, flags=%d", path, flags)
        if not path in self.data_caches:
            st_size = self.getattr(path)['st_size']
            it = ContentCache(self.kp.download(path).raw, st_size)
            self.data_caches[path] = it
        return 0

    def release(self, path, fh):
        log.debug("release: %s, fh=%s", path, str(fh))
        return 0

    def read(self, path, size, offset, fh):
        log.debug("read: %s, size=%d, offset=%d, fh=%s",
                  path, size, offset, str(fh))
        it = self.data_caches[path]
        return it.read(size, offset)

    def truncate(self, path, length, fh=None):
        log.debug("truncate: %s, length=%d, fh=%s",
                  path, length, str(fh))
        it = self.data_caches[path]
        it.truncate(length)
        node = self.get_node(path)
        node['attrs']['st_size'] = length

    def write(self, path, data, offset, fh):
        log.debug("write: %s, data=%s, offset=%d, fh=%s",
                  path, cap_string(data, 10),  offset, str(fh))
        it = self.data_caches[path]
        it.write(data, offset)
        node = self.get_node(path)
        node['attrs']['st_size'] = offset + len(data)
        return len(data)

    def flush(self, path, fh):
        log.debug("flush: %s, fh=%s", path, str(fh))
        it = self.data_caches[path]
        it.flush(path, self.kp)
        node = self.get_node(path)
        node['attrs']['st_mtime'] = time.time()
        return 0

    def create(self, path, mode=0644, fi=None):
        log.debug("create: %s, mode: %d, fi=%s", path, mode, str(fi))
        self.data_caches[path] = ContentCache()
        self.create_node(path, False)
        name = os.path.basename(path)
        if name.startswith('.~') or name.startswith('~'):
            return
        self.kp.upload(path, '', True)
        return 0


def echo_msg():
    print(u"|------------------------------------------------")
    print(u"|            Kuaipan.cn Fuse System             |")
    print(u"|   Author: maxint                              |")
    print(u"|   Link：http://github.com/maxint/kuaipan      |")
    print(u"|   Email：NOT_SPAM_lnychina{AT}gmail{DOT}com   |")
    print(u"|------------------------------------------------")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Kuaipan Fuse System')
    parser.add_argument('mount_point', nargs='?', default='Kuaipan')
    parser.add_argument('-D', '--debug', action='store_true')
    args = parser.parse_args()

    if args.debug:
        log_to_stdout(log)

    echo_msg()

    # Call ipython when raising exception
    #from IPython.core import ultratb
    #sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                         #color_scheme='Linux',
                                         #call_pdb=1)

    # Create Kuaipan Client
    CACHED_KEYFILE = '.cached_kuaipan_key.json'
    try:
        kp = kuaipan.load(CACHED_KEYFILE)
    except:
        def authoriseCallback(url):
            import webbrowser
            webbrowser.open(url)
            return input('Please input the verifier:')

        CONSUMER_KEY = 'xcNBQcp5oxmRanaC'
        CONSUMER_SECRET = 'ilhYuLMWpyVDaLm4'
        kp = kuaipan.Kuaipan(CONSUMER_KEY, CONSUMER_SECRET)
        kp.authorise(authoriseCallback)
        kp.save(CACHED_KEYFILE)

    import os
    fuse = fuse.FUSE(KuaipanFuse(kp),
                     args.mount_point,
                     foreground=True,
                     uid=os.getuid(),
                     gid=os.getgid())
