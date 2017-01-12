#!/usr/bin/env python
# coding: utf-8

import os
import unittest
import kpfuse

class TestKuaiPanFuse(unittest.TestCase):
    mount_point = '/tmp/kpfuse_mnt'

    def setUp(self):
        if not os.path.exists(self.mount_point):
            os.makedirs(self.mount_point)
        kpfuse.safe_launch(mount_point=self.mount_point, verbose=True)

    def _get_path(self, *args):
        return os.path.join(self.mount_point, *args)

    def test_create_file(self):
        tmp_path = self._get_path('__tmp__.txt')
        content = "hi"
        open(tmp_path, 'w').write(content)
        read_content = open(tmp_path).read()
        self.assertEqual(read_content, content)
        os.remove(tmp_path)

    def tearDown(self):
        import subprocess
        subprocess.check_call('sudo umount %s' % self.mount_point)
        os.removedirs(self.mount_point)