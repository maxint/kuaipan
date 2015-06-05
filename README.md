# Kuaipan FUSE FileSystem

FUSE file system for kuaipan.cn. Access the cloud data in kuaipan.cn as local disk data.


# Features

- Access cloud data as local data without download data manually.
- Local file cache to speed up access performance.
- Support multiple accounts.


# Install

```
pip install git+git://github.com/maxint/kuaipan [--user]
```
Note: use "--user" to install into user directory.


# Requirements

- fusepy
- oauthlib
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


# Debug & Bug Report

This fuse file system is far from perfect and may suck sometimes. Bug reports and any other contributions are welcomed. 
Logging is enabled by default. Additionally, run `kpfs` command with `-D` to enable debug logging for more internal information.
The log file locates at `/tmp/kpfuse.log`. If you has any issue, please paste the log as well.


# Local Cache

The account data and local cache files are stored at `~/.kpfuse`. 
Cache files that elder than 30 days would be deleted.
You could also clean the cache objects in `~/.kpfuse/<account email>/object/` manually, when local cache occupied too much disk space
or cache objects are corrupted (when bugs existed).