#! /usr/bin/env python2
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
import errno
import cache
import os

import logging
log = logging.getLogger('kpfuse')


def log_to_stdout(log):
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(fmt)
    log.addHandler(ch)


def get_time(time_str):
    return time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M:%S"))


def update_mtime(attrs, mtime=None):
    if mtime is None:
        mtime = time.time()
    attrs['st_mtime'] = attrs['st_atime'] = mtime


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
    def __init__(self, kp, pooldir):
        self.kp = kp
        self.caches = cache.CachePool(pooldir)
        self.tree = dict()
        self.build('/', self.tree)

    def build(self, path, node):
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
                },
                ...
            }
        }
        """
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
                                             attrs=create_stat2(x))
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
                return node

            if 'files' not in node:
                if self.build(cur_dir, node) is None:
                    return
            node = node.get('files').get(name)
            if node is None:
                return
            cur_dir = os.path.join(cur_dir, name)

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
            update_mtime(pnode['attrs'])
            return pnode['files'].pop(aname, None)

    def insert_node(self, path, node):
        adir, aname = os.path.split(path)
        pnode = self.get_node(adir)
        if pnode:
            pnode['files'][aname] = node
            pnode['dirs'].append(aname)
            update_mtime(pnode['attrs'])
        return node

    # ----------------------------------------------------

    def access(self, path, amode):
        return 0

    def getattr(self, path, fh=None):
        node = self.get_node(path, False)
        if not node:
            raise fuse.FuseOSError(errno.ENOENT)
        return node['attrs']

    def readdir(self, path, fh):
        return self.get_node(path, True)['dirs']

    def rename(self, old, new):
        self.kp.move(old, new)
        # update
        node = self.pop_node(old)
        if node:
            self.insert_node(new, node)

    def mkdir(self, path, mode=0644):
        self.kp.mkdir(path)
        self.create_node(path, True)

    def rmdir(self, path):
        self.kp.delete(path)
        self.pop_node(path)

    def unlink(self, path):
        self.rmdir(path)
        self.caches.remove(path)

    def open(self, path, flags):
        if path is not self.caches:
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
        node = self.get_node(path)
        node['attrs']['st_size'] = length
        update_mtime(node['attrs'])

    def write(self, path, data, offset, fh):
        it = self.caches[path]
        it.write(data, offset)
        node = self.get_node(path)
        node['attrs']['st_size'] = offset + len(data)
        update_mtime(node['attrs'])
        return len(data)

    def flush(self, path, fh):
        self.caches[path].flush(path, self.kp)
        node = self.get_node(path)
        update_mtime(node['attrs'])
        return 0

    def create(self, path, mode=0644, fi=None):
        self.caches.add(path)
        self.create_node(path, False)
        name = os.path.basename(path)
        if name.startswith('.~') or name.startswith('~'):
            return 0
        self.kp.upload(path, '', True)
        return 0


def echo_msg():
    print(u"|------------------------------------------------")
    print(u"|            Kuaipan.cn Fuse System             |")
    print(u"|   Author: maxint                              |")
    print(u"|   Link:   http://github.com/maxint/kuaipan    |")
    print(u"|   Email:  NOT_SPAM_lnychina{AT}gmail{DOT}com  |")
    print(u"|------------------------------------------------")


def ipdb_debug():
    # Call ipython when raising exception
    try:
        from IPython.core import ultratb
        sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                             color_scheme='Linux',
                                             call_pdb=1)
    except:
        log.warn('Install IPython before enable ipdb')

if __name__ == "__main__":
    import argparse

    def readable_dir(path):
        if not os.path.isdir(path):
            msg = '"{}" is not a valid directory'.format(path)
            raise argparse.ArgumentTypeError(msg)
        return path

    parser = argparse.ArgumentParser(description='Kuaipan Fuse System')
    parser.add_argument('mount_point', type=readable_dir,
                        help='Mount point')
    parser.add_argument('-D', '--verbose', action='store_true',
                        help='Output logging')
    parser.add_argument('--ipdb', action='store_true',
                        help='Enable ipdb for debug')
    parser.add_argument('--foreground', '-f', action='store_true',
                        help='Run in foreground, for debug')
    args = parser.parse_args()

    if args.verbose:
        log_to_stdout(log)

    if args.ipdb:
        ipdb_debug()

    echo_msg()
    print 'Mount kuaipan to "{}"'.format(args.mount_point)

    # Create Kuaipan Client
    import tempfile
    tempdir = os.path.join(tempfile.gettempdir(), 'kuaipan')
    if not os.path.exists(tempdir):
        os.mkdir(tempdir)

    CACHED_KEYFILE = os.path.join(tempdir, 'cached_key.json')
    try:
        kp = kuaipan.load(CACHED_KEYFILE)
    except:
        def authoriseCallback(url):
            import webbrowser
            webbrowser.open(url)
            print 'Open in browser: ' + url
            return input('Please input the verifier:')

        CONSUMER_KEY = 'xcNBQcp5oxmRanaC'
        CONSUMER_SECRET = 'ilhYuLMWpyVDaLm4'
        kp = kuaipan.Kuaipan(CONSUMER_KEY, CONSUMER_SECRET)
        kp.authorise(authoriseCallback)
        kp.save(CACHED_KEYFILE)

    fuseop = KuaipanFuse(kp, tempdir)
    if not args.verbose:
        # disable logging
        fuseop.__call__ = None
    fuse.FUSE(fuseop,
              args.mount_point,
              foreground=args.foreground,
              uid=os.getuid(),
              gid=os.getgid(),
              nonempty=True)
