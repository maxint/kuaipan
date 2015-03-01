# Kuaipan FUSE FileSystem

FUSE file system for kuaipan.cn


# Install

```
pip install git+git://github.com/maxint/kuaipan [--user]
```
Note: use "--user" to install into user directory.


# Requirements

- fusepy
- requests
- requests-oauthlib


# Usage

Mount your kuaipan.cn cloud driver to given mount directory:
```
kpfs <mount point>
```

Umount it:
```
umount <mount point>
```

Help:
```
kpfs -h
```