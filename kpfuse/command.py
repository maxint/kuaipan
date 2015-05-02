# coding: utf-8

import os
import fuse
import logging
import json

import kpfuse
import kuaipan
import oauth_callback
import version
from error import setup_logging
from error import remove_log_handler

log = logging.getLogger(__name__)


def make_dirs(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def launch(mount_point, username, foreground=False, verbose=False):
    setup_logging(os.path.join(os.path.dirname(__file__), 'logging.json'))
    if not verbose:
        remove_log_handler('kpfuse', 'console')

    log.info('Mount point: %s', mount_point)

    profile_path = os.path.expanduser('~/.kpfuse/profile.json')
    if username is None:
        try:
            with open(profile_path, 'rt') as f:
                d = json.load(f)
                username = d['last_username']
        except:
            pass

    kp = None
    if username:
        profile_dir = os.path.expanduser('~/.kpfuse/' + username)
        cache_path = os.path.join(profile_dir, 'cached_key.json')
        if os.path.exists(cache_path):
            log.debug('Load cached key from %s', cache_path)
            try:
                kp = kuaipan.load(cache_path)
                kp.account_info()
            except Exception, e:
                log.warn(e.message)
                kp = None
        else:
            log.warn('Can not find user data directory: %s', profile_dir)

    if kp is None:
        kp = kuaipan.Kuaipan('xcNBQcp5oxmRanaC', 'ilhYuLMWpyVDaLm4')
        kp.authorise(oauth_callback.http_authorise)
        username = kp.account_info()['user_name']
        log.debug('Create cached key')
        cache_dir = os.path.expanduser('~/.kpfuse/' + username)
        cache_path = os.path.join(cache_dir, 'cached_key.json')
        log.debug('Save cached key to %s', cache_path)
        make_dirs(cache_dir)
        kp.save(cache_path)

    log.info('Login username: %s', username)

    # save last username
    with open(profile_path, 'wt') as f:
        d = json.dumps(dict(last_username=username))
        f.write(d)

    log.debug('Create KuaipanFuse')
    fuse_op = kpfuse.KuaipanFuse(kp, os.path.expanduser('~/.kpfuse/' + username))
    log.info('Start FUSE file system')
    fuse.FUSE(fuse_op,
              mount_point,
              foreground=foreground,
              uid=os.getuid(),
              gid=os.getgid(),
              nonempty=True,
              nothreads=True,  # on multiple thread
              ro=False)  # readonly


def main():
    import argparse

    def readable_dir(path):
        if not os.path.isdir(path):
            msg = '"{}" is not a valid directory'.format(path)
            raise argparse.ArgumentTypeError(msg)
        return path

    parser = argparse.ArgumentParser(description='Kuaipan Fuse File System')
    parser.add_argument('mount_point', type=readable_dir,
                        help='Mount point directory')
    parser.add_argument('-D', '--verbose', action='store_true',
                        help='Enable logging')
    parser.add_argument('--foreground', '-f', action='store_true',
                        help='Run in foreground, for debug')
    parser.add_argument('-u', '--username', nargs='?',
                        help='user name (e.g. <email>)')
    parser.add_argument('--version', '-V', action='version',
                        version='%(prog)s {version}, by {author} <{email}>'.format(version=version.__version__,
                                                                                   author=version.__author__,
                                                                                   email=version.__email__))

    args = parser.parse_args()

    launch(**vars(args))


if __name__ == "__main__":
    main()