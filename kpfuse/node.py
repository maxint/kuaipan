# coding: utf-8

import os
import stat
import time
from kuaipan import Kuaipan


class DirNodeAttribute(object):
    """
        st_mode:
        st_size:
        st_nlink:
        st_ctime:
        st_atime:
        st_mtime:
    """
    def __init__(self, ctime=time.time(), mtime=None):
        if mtime is None:
            mtime = ctime
        self.nlink = 2
        self.mode = stat.S_IFDIR | 0644
        self.ctime = ctime
        self.mtime = mtime

    def update(self, mtime=None):
        if mtime is None:
            mtime = time.time()
        self.mtime = mtime

    def get(self):
        return dict(st_mode=self.mode,
                    st_nlink=self.nlink,
                    st_ctime=self.ctime,
                    st_mtime=self.mtime,
                    st_atime=self.mtime)


class FileNodeAttribute(DirNodeAttribute):
    def __init__(self, size=0, ctime=time.time(), mtime=None):
        super(FileNodeAttribute, self).__init__(ctime, mtime)
        self.size = size
        self.nlink = 1
        self.mode = stat.S_IFREG | 0644

    def get(self):
        d = super(FileNodeAttribute, self).get()
        d.update(dict(st_size=self.size))
        return d

    def set_size(self, size):
        self.size = size
        self.update()


class AbstractNode(object):
    def __init__(self, kp, path):
        self.kp = kp
        self.path = path
        self.attribute = None


class FileNode(AbstractNode):
    def __init__(self, kp, path):
        super(FileNode, self).__init__(kp, path)
        self.attribute = FileNodeAttribute()


class DirNode(AbstractNode):
    def __init__(self, kp, path, nodes=None):
        super(DirNode, self).__init__(kp, path)
        self.attribute = DirNodeAttribute()
        self.valid = nodes is not None
        self.nodes = dict() if nodes is None else nodes

    def insert(self, name, node):
        self.build()
        self.nodes[name] = node
        self.attribute.update()

    def remove(self, name):
        self.build()
        node = self.nodes.pop(name)
        self.attribute.update()
        return node

    def get(self, name):
        self.build()
        return self.nodes.get(name)

    def names(self):
        self.build()
        return self.nodes.keys() + ['.', '..']

    def build(self):
        if self.valid:
            return

        meta = self.kp.metadata(self.path)
        assert meta, 'Could not find directory {} at server'.format(self.path)
        assert meta.get('path') == '/' or meta['type'] == 'folder'

        children_nodes = dict()
        for x in meta.get('files', []):
            child_name = x['name']
            child_path = self.path + '/' + child_name
            child_node = FileNode(self.kp, child_path) if x['type'] == 'file' else DirNode(self.kp, child_path)
            child_node.attribute = create_stat(x)
            children_nodes[child_name] = child_node

        self.valid = True
        self.nodes = children_nodes


def get_time(time_str):
    if time_str:
        return time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M:%S"))
    else:
        return time.time()


def create_stat(meta):
    ctime = get_time(meta.get('create_time'))
    mtime = get_time(meta.get('modify_time'))
    if meta.get('path') == '/' or meta['type'] == 'folder':
        return DirNodeAttribute(ctime, mtime)
    else:
        return FileNodeAttribute(meta.get('size', 0), ctime, mtime)


class NodeTree:
    def __init__(self, kp, root_dir):
        assert isinstance(kp, Kuaipan)
        self.kp = kp
        self.root_dir = root_dir
        self.tree = DirNode(self.kp, '/')

    def get(self, path):
        if path == '/':
            return self.tree

        names = path.strip('/').split('/')
        node = self.tree
        for name in names:
            if node is None or isinstance(node, FileNode):
                return node

            assert isinstance(node, DirNode)
            node.build()
            node = node.get(name)

        return node

    def create(self, path, isdir):
        node = DirNode(self.kp, path, dict()) if isdir else FileNode(self.kp, path)
        return self.insert(path, node)

    def remove(self, path):
        dir_path, base_name = os.path.split(path)
        node = self.get(dir_path)
        if node:
            return node.remove(base_name)

    def insert(self, path, node):
        dir_path, base_name = os.path.split(path)
        parent_node = self.get(dir_path)
        assert isinstance(parent_node, DirNode)
        if parent_node:
            parent_node.insert(base_name, node)

    def move(self, path, new_path):
        node = self.remove(path)
        if node:
            self.insert(new_path, node)
        return node