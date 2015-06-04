# coding: utf-8

import os
import stat
import time
from kuaipan import KuaiPan


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


class AbstractNode(object):
    def __init__(self, path):
        self.path = path
        self.attribute = None

    def update_meta(self, kp):
        """Update meta information for node"""
        meta = kp.metadata(self.path)
        self.attribute = create_stat(meta)


class FileNode(AbstractNode):
    def __init__(self, path):
        super(FileNode, self).__init__(path)
        self.attribute = FileNodeAttribute()


class DirNode(AbstractNode):
    def __init__(self, path, nodes=None):
        super(DirNode, self).__init__(path)
        self.attribute = DirNodeAttribute()
        self.valid = nodes is not None
        self.nodes = dict() if nodes is None else nodes

    def insert(self, name, node):
        assert self.valid
        self.nodes[name] = node

    def remove(self, name):
        assert self.valid
        node = self.nodes.pop(name)
        return node

    def get(self, name):
        assert self.valid
        return self.nodes.get(name)

    def names(self):
        assert self.valid
        return self.nodes.keys()

    def build(self, kp):
        if self.valid:
            return

        meta = kp.metadata(self.path)
        assert meta, 'Could not find directory {} at server'.format(self.path)
        assert meta.get('path') == '/' or meta['type'] == 'folder'

        children_nodes = dict()
        for x in meta.get('files', []):
            child_name = x['name']
            child_path = os.path.join(self.path, child_name)
            child_node = FileNode(child_path) if x['type'] == 'file' else DirNode(child_path)
            child_node.attribute = create_stat(x)
            children_nodes[child_name] = child_node

        self.nodes = children_nodes
        self.valid = True


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
    def __init__(self, kp):
        assert isinstance(kp, KuaiPan)
        self.kp = kp
        self.tree = DirNode('/')

    def get(self, path):
        """
        :rtype: DirNode
        """
        if path == '/':
            return self.tree

        names = [x for x in path.split('/') if x]
        node = self.tree
        for name in names:
            if node is None or isinstance(node, FileNode):
                return node
            """:type node: DirNode"""
            node.build(self.kp)
            node = node.get(name)

        if isinstance(node, DirNode):
            node.build(self.kp)

        return node

    def create(self, path, isdir):
        """
        :rtype: AbstractNode
        """
        node = DirNode(path, dict()) if isdir else FileNode(path)
        self.insert(path, node)
        return node

    def remove(self, path):
        """
        :rtype: AbstractNode
        """
        dir_path, base_name = os.path.split(path)
        node = self.get(dir_path)
        if node:
            return node.remove(base_name)

    def insert(self, path, node):
        dir_path, base_name = os.path.split(path)
        parent_node = self.get(dir_path)
        """:type: DirNode"""
        if parent_node:
            parent_node.insert(base_name, node)

    def move(self, path, new_path):
        node = self.remove(path)
        if node:
            node.path = new_path
            self.insert(new_path, node)
        return node
