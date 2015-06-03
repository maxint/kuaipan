#!/usr/bin/env python
# coding: utf-8

import os
import unittest
from kpfuse.launch import create_kuaipan_client

class TestKuaipan(unittest.TestCase):
    filename = os.path.basename(__file__)
    
    def setUp(self):
        _, self.kp = create_kuaipan_client(save_cache=False)
        self.tearDown()

    def test_kuaipan_normal_operations(self):
        c = self.kp

        print '= account_info:', c.account_info()
        print '= metadata:', c.metadata('/')
        print '= upload:', c.upload(self.filename, open(__file__, 'rb'))
        print '= upload:', c.upload('tmp.txt', 'hi')
        print '= metadata:', c.metadata(self.filename)
        print '= mkdir:', c.mkdir('_tmp_')
        print '= move:', c.move('_tmp_', '_tmp2_')
        print '= copy:', c.copy('_tmp2_', '_tmp3_')
        print '= copy_ref:', c.copy_ref(self.filename)
        print '= download:', c.download(self.filename)

    def tearDown(self):
        # clean up
        self.kp.delete(self.filename, force=True)
        self.kp.delete('tmp.txt', force=True)
        self.kp.delete('_tmp_', force=True)
        self.kp.delete('_tmp2_', force=True)
        self.kp.delete('_tmp3_', force=True)

    @unittest.skip('NOT implemented by kuaipan.cn')
    def test_kuaipan_advanced_operations(self):
        c = self.kp
        print '= history:', c.history(self.filename)  # history not existed
        print '= shares1', c.shares(self.filename)
        print '= shares2:', c.shares(self.filename, 'test', 'fasdfasdla')
        print '= thumbnail:', c.thumbnail(128, 128, 'Work/resume/zjg_icon.jpg')
        print '= document_view:', c.document_view('txt', 'android', self.filename)