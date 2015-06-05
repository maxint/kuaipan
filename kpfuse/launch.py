# coding: utf-8

import os
import fuse
import logging
import json

import kpfuse
import kuaipan
import oauth_callback
import version
from errors import setup_logging
from errors import remove_log_handler

log = logging.getLogger(__name__)


def make_dirs(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def get_profile_path():
    return os.path.expanduser('~/.kpfuse/profile.json')


def get_profile_dir(username):
    return os.path.expanduser('~/.kpfuse/' + username)


def get_key_cache_path(username):
    return os.path.join(get_profile_dir(username), 'cached_key.json')


def create_kuaipan_client(username=None, save_cache=True):
    profile_path = get_profile_path()
    if username is None:
        try:
            with open(profile_path, 'rt') as f:
                d = json.load(f)
                username = d['last_username']
        except:
            pass

    kp = None
    if username:
        cache_path = get_key_cache_path(username)
        if os.path.exists(cache_path):
            log.debug('Load cache key from %s', cache_path)
            from oauthlib.oauth2 import TokenExpiredError
            try:
                kp = kuaipan.load(cache_path)
                kp.account_info()
            except TokenExpiredError:
                log.warn('Re-login as OAuth2 token is expired')
                kp = None
            except Exception, e:
                log.warn('Invalid OAuth2 keys: %s', e.message)
                raise
        else:
            log.warn('Can not find cache key file %s', cache_path)

    if kp is None:
        kp = kuaipan.KuaiPan('xcNBQcp5oxmRanaC', 'ilhYuLMWpyVDaLm4')
        kp.authorise(oauth_callback.http_authorise)
        username = kp.account_info()['user_name']
        if save_cache:
            save_key_cache(kp, username)

    log.info('Login username: %s', username)

    # save last username
    if save_cache:
        with open(profile_path, 'wt') as f:
            json.dump(dict(last_username=username), f, indent=2)

    return username, kp


def create_kuaipan_fuse_operations(username=None, save_cache=True):
    log.debug('Creating Kuaipan client')
    username, kp = create_kuaipan_client(username, save_cache)

    log.debug('Create KuaipanFuse')
    return kpfuse.KuaipanFuseOperations(kp, get_profile_dir(username))


def save_key_cache(kp, username):
    """
    :type kp: kuaipan.KuaiPan
    """
    make_dirs(get_profile_dir(username))
    cache_path = get_key_cache_path(username)
    log.info('Save cached key to %s', cache_path)
    kp.save(cache_path)


def create_logger(foreground=False, verbose=False, **kwargs):
    setup_logging(os.path.join(os.path.dirname(__file__), 'logging.json'), **kwargs)
    if not foreground:
        remove_log_handler('kpfuse', 'console')
        log.info('Disable console output')
    if verbose:
        logging.getLogger('kpfuse').setLevel(logging.DEBUG)


def launch(mount_point, username=None, foreground=False, verbose=False):
    create_logger(foreground, verbose)

    log.info('Mount point: %s', mount_point)
    fuse_op = create_kuaipan_fuse_operations(username)

    log.info('Start FUSE file system')
    fuse.FUSE(fuse_op,
              mount_point,
              foreground=foreground,
              uid=os.getuid(),
              gid=os.getgid(),
              # nonempty=True, # fuse: unknown option `nonempty' on OS X
              nothreads=False,  # on multiple thread
              ro=False)  # readonly


def safe_launch(**kwargs):
    try:
        launch(**kwargs)
    except:
        log.exception('kpfuse failed')
        raise


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
                        help='Enable debug logging')
    parser.add_argument('--foreground', '-f', action='store_true',
                        help='Run in foreground, for debug')
    parser.add_argument('-u', '--username', nargs='?',
                        help='user name (e.g. <email>)')
    parser.add_argument('--version', '-V', action='version',
                        version='%(prog)s {version}, by {author} <{email}>'.format(version=version.__version__,
                                                                                   author=version.__author__,
                                                                                   email=version.__email__))

    args = parser.parse_args()
    safe_launch(**vars(args))


if __name__ == "__main__":
    main()
