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
#import sys; sys.path.insert(0, '/home/maxint/code/requests-oauthlib')

from requests_oauthlib import OAuth1Session
import json
import os
from urllib import quote

API_VERSION = 1
API_HOST = 'https://openapi.kuaipan.cn/'
CONV_HOST = 'http://conv.kuaipan.cn/'
CONTENT_HOST = 'http://api-content.dfs.kuaipan.cn/'
AUTH_URL = 'https://www.kuaipan.cn/api.php?ac=open&op=authorise'


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
        self.oauth.fetch_request_token(API_HOST + 'open/requestToken')

        # authorize
        authorization_url = self.oauth.authorization_url(AUTH_URL)
        if callback:
            verifier = callback(authorization_url)
        else:
            print 'Please go here and authorize, ', authorization_url
            verifier = raw_input('Paste the verifier here: ')

        # accessToken
        self.oauth.fetch_access_token(API_HOST + 'open/accessToken', verifier)

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

    def build_url(self, url, api='API', path=None):
        HOSTS = {
            'API': API_HOST,
            'CONV': CONV_HOST,
            'CONTENT': CONTENT_HOST,
        }
        if path:
            if isinstance(path, unicode):
                path = path.encode('utf-8')
            url = os.path.join(url, self.root, quote(path.strip('/')))
        if api in HOSTS:
            return os.path.join(HOSTS.get(api, ''), str(API_VERSION), url)
        else:
            return url

    def get(self, url, api='API', path=None, **kargs):
        url = self.build_url(url, api, path)
        r = self.oauth.get(url, **kargs)
        if r.status_code == 200:
            return r
        return r
        #else:
            #raise Exception()

    def account_info(self):
        return self.get('account_info').json()

    def metadata(self, path, recurse=None, file_limit=None,
                 page=None, page_size=None,
                 filter_ext=None, sort_by=None):
        return self.get('metadata', path=path, params={
            'list': recurse,
            'file_limit': file_limit,
            'page': page,
            'page_size': page_size,
            'filter_ext': filter_ext,
            'sort_by': sort_by,
        }).json()

    def shares(self, path, name=None, access_code=None):
        return self.get('shares', path=path, params={
            'name': name,
            'access_code': access_code,
        }).json()

    def history(self, path):
        return self.get('history', path=path).json()

    def mkdir(self, path):
        return self.get('fileops/create_folder', params={
            'root': self.root,
            'path': path,
        }).json()

    def delete(self, path, to_recycle=None):
        return self.get('fileops/delete', params={
            'root': self.root,
            'path': path,
            'to_recycle': to_recycle,
        })

    def move(self, from_path, to_path):
        return self.get('fileops/move', params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
        })

    def copy(self, from_path, to_path, from_copy_ref=None):
        return self.get('fileops/copy', params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
            'to_path': to_path,
        })

    def copy_ref(self, path):
        return self.get('copy_ref', path=path).json()

    def upload(self, path, data, overwrite=True, source_ip=None):
        host = self.get('fileops/upload_locate', api='CONTENT', params={
            'source_ip': source_ip
        }).json().get('url')
        url = os.path.join(host, str(API_VERSION), 'fileops/upload_file')
        return self.oauth.post(url, params={
            'root': self.root,
            'path': path,
            'overwrite': overwrite,
        }, files=dict(file=data)).json()

    def download(self, path, rev=None):
        """
        Download file and return requests.Response

        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
        """
        return self.get('fileops/download_file', api='CONTENT', params={
            'root': self.root,
            'path': path,
            'rev': rev,
        }, stream=True)

    def thumbnail(self, width, height, path):
        '''
        TYPE_IMG = ('gif', 'png', 'jpg', 'bmp', 'jpeg', 'jpe')
        '''
        return self.get('fileops/thumbnail', api='CONV', params={
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
        return self.get('fileops/documentView', api='CONV', params={
            'root': self.root,
            'path': path,
            'type': doctype,
            'view': view,
            'zip': 1 if iszip else 0,
        })


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
    print '= account_info:', c.account_info()
    print '= metadata:', c.metadata('/')
    print '= upload:', c.upload(fname, open(__file__, 'rb'))
    print '= upload:', c.upload('tmp.txt', 'hi')
    print '= metadata:', c.metadata(fname)
    print '= history:', c.history(fname)  # history not existed
    print '= shares1', c.shares(fname)
    print '= shares2:', c.shares(fname, 'test', 'fasdfasdla')
    print '= mkdir:', c.mkdir('_tmp_')
    print '= move:', c.move('_tmp_', '_tmp2_')
    print '= copy:', c.copy('_tmp2_', '_tmp3_')
    print '= delete1:', c.delete('_tmp2_')
    print '= delete2:', c.delete('_tmp3_')
    print '= copy_ref:', c.copy_ref(fname)
    print '= download:', c.download(fname)
    print '= thumbnail:', c.thumbnail(128, 128, 'Work/resume/zjg_icon.jpg')
    print '= document_view:', c.document_view('txt', 'android', fname)
    print 'Done.'
