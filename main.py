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


def create_st(meta):
    if meta.get('path') == '/':
        st = dict(st_mode=(stat.S_IFDIR | 0644), st_nlink=1)
        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time.time()
        return st
    if meta['type'] == 'folder':
        st = dict(st_mode=(stat.S_IFDIR | 0644), st_nlink=1)
    else:
        st = dict(st_mode=(stat.S_IFREG | 0644), st_nlink=1,
                  st_size=meta['size'])
    st['st_ctime'] = get_time(meta['create_time'])
    st['st_mtime'] = st['st_atime'] = get_time(meta['modify_time'])
    return st


class TreeCache():
    def __init__(self, kp):
        self.kp = kp
        self.tree = dict()
        self.build('/', self.tree)

    def get_metadata(self, path):
        meta = self.kp.metadata(path)
        if meta and 'path' in meta:
            return meta

    def build(self, path, node):
        meta = self.get_metadata(path)
        if meta is None:
            return

        node['st'] = create_st(meta)
        if meta.get('path') == '/' or meta['type'] == 'folder':
            node['type'] = 'folder'
            files = meta.get('files', [])
            if 'dirs' not in node:
                node['dirs'] = [x['name'] for x in files] + ['.', '..']
            if 'files' not in node:
                fnodes = dict()
                for x in files:
                    fnodes[x['name']] = dict(st=create_st(x),
                                             type=x['type'])
                node['files'] = fnodes
        else:
            node['type'] = 'file'

        return node

    def getnode(self, path, dirs=False):
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

        #if dirs:
            #print path; import ipdb; ipdb.set_trace()
        if node.get('type') == 'folder' and 'dirs' not in node and dirs:
            self.build(path, node)
        return node

    def getattr(self, path):
        node = self.getnode(path, False)
        if node:
            return node['st']

    def readdir(self, path):
        node = self.getnode(path, True)
        return node['dirs']


class KuaipanFuse(fuse.LoggingMixIn, fuse.Operations):
    def __init__(self, kp):
        self.kp = kp
        self.now = time.time()
        self.tree = TreeCache(kp)
        self.read_cache = dict()

    def get_metadata(self, path):
        meta = self.kp.metadata(path)
        if meta and 'path' in meta:
            return meta

    #文件属性
    def getattr(self, path, fh=None):
        log.debug("getattr: %s", path)
        if path == '/':
            st = dict(st_mode=(stat.S_IFDIR | 0644), st_nlink=1)
            st['st_ctime'] = st['st_mtime'] = st['st_atime'] = self.now
            return st

        st = self.tree.getattr(path)
        if not st:
            log.debug("getattr: %s not exists!", path)
            raise fuse.FuseOSError(errno.ENOENT)
        return st

    #文件列表
    def readdir(self, path, fh):
        log.debug("readdir: %s", path)
        return self.tree.readdir(path)

    #重命名/移动文件
    def rename(self, old, new):
        log.debug("rename %s to %s", old, new)
        self.kp.move(old, new)
        #self.all_dir = self.walk_recursion("/")

    #创建目录
    def mkdir(self, path, mode=0644):
        log.debug("mkdir: %s", path)
        self.kp.mkdir(path)
        #self.all_dir = self.walk_recursion("/")

    #删除目录
    def rmdir(self, path):
        log.debug("rmdir: %s", path)
        self.kp.delete(path)
        #self.all_dir = self.walk_recursion("/")

    #删除文件
    unlink = rmdir

    #读文件
    def read(self, path, size, offset, fh):
        log.debug("read: %s, size: %d, offset: %d", path, size, offset)
        if not path in self.read_cache:
            class ContentCache():
                def __init__(self, r, size):
                    self.csize = size
                    self.gen = r.iter_content(size)
                    self.buf = ''
                    self.bufsz = 0
                    self.eof = False

                def align_count(self, size):
                    return (size + self.csize - 1) / self.csize

                def read(self, size, offset):
                    total = size + offset
                    if self.bufsz < total and not self.eof:
                        count = self.align_count(total - self.bufsz)
                        print count
                        try:
                            for i in range(count):
                                self.buf += self.gen.next()
                        except (StopIteration, ValueError):
                            self.eof = True
                        self.bufsz = len(self.buf)
                    fsize = min(total, self.bufsz)
                    return self.buf[offset:fsize]

            it = ContentCache(self.kp.download(path), 4096)
            self.read_cache[path] = it
        else:
            it = self.read_cache[path]
        return it.read(size, offset)

    #写文件
    def write(self, path, data, offset, fh):
        log.debug("write %s, data: %s, offset: %d",
                  path, cap_string(data, 10),  offset)
        self.kp.upload(path, data, True)
        #self.all_dir = self.walk_recursion("/")
        return len(data)

    #创建文件
    def create(self, path, mode=0644, fi=None):
        log.debug("create %s", path)
        self.kp.upload(path, '', True)
        #self.all_dir = self.walk_recursion("/")
        return 0


def echo_msg():
    print(u"|------------------------------------------------")
    print(u"|            Kuaipan.cn Fuse System             |")
    print(u"|   Author: maxint                              |")
    print(u"|   Link：http://github.com/maxint/kuaipan      |")
    print(u"|   Email：NOT_SPAM_lnychina{AT}gmail{DOT}com   |")
    print(u"|------------------------------------------------")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        mount_point = 'Kuaipan'
        #print("Usage: %s <point>" % sys.argv[0])
        #exit(1)
    else:
        mount_point = sys.argv[1]

    log_to_stdout(log)
    echo_msg()

    # Call ipython when raising exception
    from IPython.core import ultratb
    sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                         color_scheme='Linux',
                                         call_pdb=1)

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
                     mount_point,
                     foreground=True,
                     uid=os.getuid(),
                     gid=os.getgid())
