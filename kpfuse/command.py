# coding: utf-8

import os
import fuse

import kpfuse
import kuaipan
import oauth_callback
import version
from error import setup_logging


def echo_msg():
    print(u"|------------------------------------------------")
    print(u"|            Kuaipan.cn Fuse System             |")
    print(u"|   Author: maxint                              |")
    print(u"|   Link:   http://github.com/maxint/kuaipan    |")
    print(u"|   Email:  NOT_SPAM_lnychina{AT}gmail{DOT}com  |")
    print(u"|------------------------------------------------")


def main():
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
    parser.add_argument('--foreground', '-f', action='store_true',
                        help='Run in foreground, for debug')
    parser.add_argument('--version', '-V', action='version',
                        version='%(prog)s {version}, by {author} <{email}>'.format(version=version.__version__,
                                                                                   author=version.__author__,
                                                                                   email=version.__email__))

    args = parser.parse_args()

    if args.verbose:
        setup_logging(os.path.join(os.path.dirname(__file__), 'logging.json'))

    echo_msg()
    print('Mount kuaipan to "%s"' % args.mount_point)

    # Create Kuaipan Client
    tempdir = os.path.expanduser('~/.kpfuse/maxint@foxmail.com/.kpfs')
    if not os.path.exists(tempdir):
        os.mkdir(tempdir)

    CACHED_KEYFILE = os.path.join(tempdir, 'cached_key.json')
    try:
        kp = kuaipan.load(CACHED_KEYFILE)
    except:
        kp = kuaipan.Kuaipan('xcNBQcp5oxmRanaC', 'ilhYuLMWpyVDaLm4')
        kp.authorise(oauth_callback.http_authorise)
        kp.save(CACHED_KEYFILE)

    fuse_op = kpfuse.KuaipanFuse(kp, tempdir)
    fuse.FUSE(fuse_op,
              args.mount_point,
              foreground=args.foreground,
              uid=os.getuid(),
              gid=os.getgid(),
              nonempty=True)


if __name__ == "__main__":
    main()