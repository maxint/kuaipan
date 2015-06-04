#!/usr/bin/env python
# coding: utf-8

import os
import fuse
import unittest
from kpfuse.launch import create_kuaipan_fuse_operations
from kpfuse.launch import create_logger

class TestKuaipanFuseOperations(unittest.TestCase):
    path = __file__
    filename = os.path.basename(path)
    log_path = '/tmp/kpfuse_operations.log'

    def setUp(self):
        os.remove(self.log_path)
        create_logger(log_path=self.log_path)
        self.fuse_op = create_kuaipan_fuse_operations(save_cache=False)
        self.kp = self.fuse_op.kp
        self.data = open(self.path, 'rb').read()
        self.kp.upload(self.filename, self.data, True)

    def test_read(self):
        total = self.fuse_op.getattr(self.filename)['st_size']

        # open twice
        fh1 = self.fuse_op.open(self.filename, os.O_RDONLY)
        read_size = total / 4
        data = self.fuse_op.read(self.filename, read_size, 0, fh1)
        self.assertEqual(data, self.data[:read_size])

        fh2 = self.fuse_op.open(self.filename, os.O_RDONLY)
        read_size = total / 3
        data = self.fuse_op.read(self.filename, read_size, 0, fh2)
        self.assertEqual(data, self.data[:read_size])

        self.fuse_op.release(self.filename, fh1)
        self.fuse_op.release(self.filename, fh2)

        # open again
        fh3 = self.fuse_op.open(self.filename, os.O_RDONLY)
        read_size = total / 3
        data = self.fuse_op.read(self.filename, read_size, 0, fh3)
        self.assertEqual(data, self.data[:read_size])
        self.fuse_op.release(self.filename, fh3)

    def tearDown(self):
        try:
            if self.fuse_op.getattr(self.filename):
                self.fuse_op.unlink(self.filename)
        except fuse.FuseOSError:
            pass
