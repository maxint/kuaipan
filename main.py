#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2014 maxint <NOT_SPAM_lnychina@gmail.com>
#
# Distributed under terms of the MIT license.

"""

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


class KuaipanFuse(fuse.LoggingMixIn, fuse.Operations):
    def __init__(self, kp):
        self.kp = kp
        self.now = time.time()

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

        meta = self.get_metadata(path)
        if not meta:
            log.debug("getattr: %s not exists!", path)
            raise fuse.FuseOSError(errno.ENOENT)

        if meta['type'] == 'folder':
            st = dict(st_mode=(stat.S_IFDIR | 0644), st_nlink=1)
        else:
            st = dict(st_mode=(stat.S_IFREG | 0644), st_nlink=1,
                      st_size=meta['size'])
        st['st_ctime'] = get_time(meta['create_time'])
        st['st_mtime'] = st['st_atime'] = get_time(meta['modify_time'])
        return st

    #文件列表
    def readdir(self, path, fh):
        log.debug("readdir: %s", path)
        meta = self.get_metadata(path)
        if not meta:
            return ['.', '..']
        else:
            dlist = meta.get('files', [])
            return [x['name'] for x in dlist] + ['.', '..']

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
        return self.kp.download(path).raw.read(size)

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
        mount_point = 'mnt'
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
