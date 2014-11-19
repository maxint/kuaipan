Introduction
------------

Python API and fuse file system for kuaipan.cn

- kuaipan.py - python API for kuaipan.cn
- main.py - Fuse file system for kuaipan.cn


Install
-------

```
    pip install -r requirements.txt
```

Usage
-----

Mount yout kuaipan to given mount directory:
```
    python2 main.py <mount point>
```

Umount it:
```
    umount <mount point>
```

Help:
```
    python2 main.py -h
```
