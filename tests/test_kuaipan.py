#!/usr/bin/env python
# coding: utf-8

import os
import unittest
from kpfuse.launch import create_kuaipan_client

class TestKuaipan(unittest.TestCase):
    def setUp(self):
        _, self.kp = create_kuaipan_client(save_cache=False)

    def test_kuaipan_normal_operations(self):
        c = self.kp
        filename = os.path.basename(__file__)

        print '= account_info:', c.account_info()
        print '= metadata:', c.metadata('/')
        print '= upload:', c.upload(filename, open(__file__, 'rb'))
        print '= upload:', c.upload('tmp.txt', 'hi')
        print '= metadata:', c.metadata(filename)
        print '= history:', c.history(filename)  # history not existed
        print '= mkdir:', c.mkdir('_tmp_')
        print '= move:', c.move('_tmp_', '_tmp2_')
        print '= copy:', c.copy('_tmp2_', '_tmp3_')
        print '= copy_ref:', c.copy_ref(filename)
        print '= download:', c.download(filename)

        # clean up
        c.delete(filename)
        c.delete('tmp.txt')
        c.delete('_tmp2_')
        c.delete('_tmp3_')

    @unittest.skip('NOT implemented by kuaipan.cn: share(), document_view()')
    def test_kuaipan_advanced_operations(self):
        c = self.kp
        filename = os.path.basename(__file__)
        print '= upload:', c.upload(filename, open(__file__, 'rb'))
        print '= shares1', c.shares(filename)
        print '= shares2:', c.shares(filename, 'test', 'fasdfasdla')
        print '= thumbnail:', c.thumbnail(128, 128, 'Work/resume/zjg_icon.jpg')
        print '= document_view:', c.document_view('txt', 'android', filename)
        c.delete(filename)