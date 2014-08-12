#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 maxint <NOT_SPAM_lnychina@gmail.com>
# Distributed under terms of the MIT license.

"""
Kuaipan Python API:
    http://www.kuaipan.cn/developers/document.htm
"""

# Add custom module
#sys.path.append('/home/maxint/code/requests-oauthlib')

from requests_oauthlib import OAuth1Session
import json
import os


API_URL = 'https://openapi.kuaipan.cn/1/'
REQUEST_TOKEN_URL = 'https://openapi.kuaipan.cn/open/requestToken'
AUTHORISE_URL = 'https://www.kuaipan.cn/api.php?ac=open&op=authorise'
ACCESS_TOKEN_URL = 'https://openapi.kuaipan.cn/open/accessToken'


class Kuaipan():
    def __init__(self, client_key, client_secret,
                 resource_owner_key=None, resource_owner_secret=None,
                 root='kuaipan'):
        self.oauth = OAuth1Session(client_key,
                                   client_secret,
                                   resource_owner_key,
                                   resource_owner_secret,
                                   signature_type=u'QUERY')
        self.root = root

    def authorise(self, callback=None):
        # requestToken
        self.oauth.fetch_request_token(REQUEST_TOKEN_URL)

        # authorize
        authorization_url = self.oauth.authorization_url(AUTHORISE_URL)
        if callback:
            verifier = callback(authorization_url)
        else:
            print 'Please go here and authorize, ', authorization_url
            verifier = raw_input('Paste the verifier here: ')

        # accessToken
        self.oauth.fetch_access_token(ACCESS_TOKEN_URL, verifier)

    def save(self, filename):
        with open(filename, 'wt') as f:
            c = self.oauth._client.client
            f.write(json.dumps({
                'client_key': c.client_key,
                'client_secret': c.client_secret,
                'resource_owner_key': c.resource_owner_key,
                'resource_owner_secret': c.resource_owner_secret,
                'root': self.root
            }))

    def account_info(self):
        return self.oauth.get(API_URL + 'account_info')

    def metadata(self, path, recurse=None, file_limit=None,
                 page=None, page_size=None,
                 filter_ext=None, sort_by=None):
        url = API_URL + 'metadata/{}/{}'.format(self.root, path)
        return self.oauth.get(url, params={
            'list': recurse,
            'file_limit': file_limit,
            'page': page,
            'page_size': page_size,
            'filter_ext': filter_ext,
            'sort_by': sort_by,
        })

    def shares(self, path, name=None, access_code=None):
        url = API_URL + 'shares/{}/{}'.format(self.root, path)
        return self.oauth.get(url, params={
            'name': name,
            'access_code': access_code,
        })

    def history(self, path):
        url = API_URL + 'history/{}/{}'.format(self.root, path)
        return self.oauth.get(url)

    def mkdir(self, path):
        url = API_URL + 'fileops/create_folder'
        return self.oauth.get(url, params={
            'root': self.root,
            'path': path,
        })

    def delete(self, path, to_recycle=None):
        url = API_URL + 'fileops/delete'
        return self.oauth.get(url, params={
            'root': self.root,
            'path': path,
            'to_recycle': to_recycle,
        })

    def move(self, from_path, to_path):
        url = API_URL + 'fileops/move'
        return self.oauth.get(url, params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
        })

    def copy(self, from_path, to_path, from_copy_ref=None):
        url = API_URL + 'fileops/copy'
        return self.oauth.get(url, params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
            'to_path': to_path,
        })

    def copy_ref(self, path):
        url = API_URL + 'copy_ref/{}/{}'.format(self.root, path)
        return self.oauth.get(url)

    def thumbnail(self, width, height, path):
        '''
        TYPE_IMG = ('gif', 'png', 'jpg', 'bmp', 'jpeg', 'jpe')
        '''
        url = 'http://conv.kuaipan.cn/1/fileops/thumbnail'
        return self.oauth.get(url, params={
            'root': self.root,
            'path': path,
            'width': width,
            'height': height,
        })

    def document_view(self, doctype, view, path, iszip=False):
        '''
        doctype = {
            'pdf', 'doc', 'wps', 'csv', 'prn',
            'xls', 'et', 'ppt', 'dps', 'txt', 'rtf'
        }
        view = {'normal', 'android', 'iPad', 'iphone'}
        zip = {0, 1}
        '''
        url = 'http://conv.kuaipan.cn/1/fileops/documentView'
        return self.oauth.get(url, params={
            'root': self.root,
            'path': path,
            'type': doctype,
            'view': view,
            'zip': 1 if iszip else 0,
        })

    def upload(self, local_path, path, overwrite=True, source_ip=None):
        url0 = 'http://api-content.dfs.kuaipan.cn/1/fileops/upload_locate'
        r = self.oauth.get(url0, params={'source_ip': source_ip})
        url = json.loads(r.text).get('url')
        url = os.path.join(url, '1/fileops/upload_file')
        return self.oauth.post(url, params={
            'root': self.root,
            'path': path,
            'overwrite': overwrite,
        }, files=dict(file=open(local_path, 'rb').read()))

    def download(self, path, local_path, rev=None):
        url = 'http://api-content.dfs.kuaipan.cn/1/fileops/download_file'
        #import ipdb; ipdb.set_trace()
        r = self.oauth.get(url, params={
            'root': self.root,
            'path': path,
            'rev': rev,
        }, stream=True)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
        return r


def load(filename):
    with open(filename, 'rt')as f:
        rs = json.load(f)
        return Kuaipan(
            rs.get('client_key'),
            rs.get('client_secret'),
            rs.get('resource_owner_key'),
            rs.get('resource_owner_secret'),
            rs.get('root'))

if __name__ == '__main__':
    # Call ipython when raising exception
    import sys
    from IPython.core import ultratb
    sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                         color_scheme='Linux',
                                         call_pdb=1)

    CACHED_KEYFILE = '.cached_kuaipan_key.json'
    try:
        c = load(CACHED_KEYFILE)
    except:
        def authoriseCallback(url):
            import webbrowser
            webbrowser.open(url)
            return input('Please input the verifier:')

        CONSUMER_KEY = 'xcNBQcp5oxmRanaC'
        CONSUMER_SECRET = 'ilhYuLMWpyVDaLm4'
        c = Kuaipan(CONSUMER_KEY, CONSUMER_SECRET)
        c.authorise(authoriseCallback)
        c.save(CACHED_KEYFILE)

    fname = os.path.basename(__file__)

    # test
    print 'account_info:', c.account_info()
    print 'metadata:', c.metadata('')
    print 'upload:', c.upload(__file__, fname)
    print 'history:', c.history(fname)  # history not existed
    print 'shares1:', c.shares(fname, 'test', 'fasdfasdla').text
    print 'shares2', c.shares(fname)
    print 'copy_ref:', c.copy_ref(fname)
    print 'mkdir:', c.mkdir('_tmp_')
    print 'move:', c.move('_tmp_', '_tmp2_')
    print 'copy:', c.copy('_tmp2_', '_tmp3_')
    print 'delete1:', c.delete('_tmp2_')
    print 'delete2:', c.delete('_tmp3_')
    print 'download:', c.download(fname, '.tmp.py')
    print 'thumbnail:', c.thumbnail(128, 128, 'Work/resume/zjg_icon.jpg')
    print 'document_view:', c.document_view('txt', 'android', fname)
    print 'Done.'
