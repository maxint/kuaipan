# coding: utf-8

"""
Kuaipan Python API:
    http://www.kuaipan.cn/developers/document.htm
"""

import os
import json
from urllib import quote
from requests_oauthlib import OAuth1Session

import errors


API_VERSION = 1
API_HOST = 'https://openapi.kuaipan.cn/'
CONV_HOST = 'http://conv.kuaipan.cn/'
CONTENT_HOST = 'http://api-content.dfs.kuaipan.cn/'
AUTH_URL = 'https://www.kuaipan.cn/api.php?ac=open&op=authorise'


class KuaiPan(object):
    def __init__(self,
                 client_key, client_secret,
                 resource_owner_key=None, resource_owner_secret=None,
                 root='kuaipan'):
        self.oauth = OAuth1Session(client_key,
                                   client_secret,
                                   resource_owner_key,
                                   resource_owner_secret,
                                   callback_uri='http://localhost:8888',
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
            cc = self.oauth.auth.client
            json.dump(
                dict(client_key=cc.client_key,
                     client_secret=cc.client_secret,
                     resource_owner_key=cc.resource_owner_key,
                     resource_owner_secret=cc.resource_owner_secret,
                     root=self.root),
                f, indent=2)

    def build_url(self, url, api='API', path=None):
        hosts = {
            'API': API_HOST,
            'CONV': CONV_HOST,
            'CONTENT': CONTENT_HOST,
        }
        if path:
            if isinstance(path, unicode):
                path = path.encode('utf-8')
            url = os.path.join(url, self.root, quote(path.strip('/')))
        if api in hosts:
            return os.path.join(hosts.get(api, ''), str(API_VERSION), url)
        else:
            return url

    def get(self, url, api='API', path=None, **kwargs):
        url = self.build_url(url, api, path)
        timeout = kwargs.pop('timeout', 1)
        r = self.oauth.get(url, timeout=timeout, **kwargs)
        """:type: Response"""
        if r.status_code == 200:
            return r
        elif r.status_code == 403:
            raise errors.FileExistedError(r)
        elif r.status_code == 404:
            raise errors.FileNotExistedError(r)
        else:
            raise errors.OAuthResponseError(r)

    def account_info(self, **kwargs):
        return self.get('account_info', **kwargs).json()

    def metadata(self, path, recurse=None, file_limit=None,
                 page=None, page_size=None,
                 filter_ext=None, sort_by=None, **kwargs):
        return self.get('metadata', path=path, params={
            'list': recurse,
            'file_limit': file_limit,
            'page': page,
            'page_size': page_size,
            'filter_ext': filter_ext,
            'sort_by': sort_by,
        }, **kwargs).json()

    def shares(self, path, name=None, access_code=None, **kwargs):
        return self.get('shares', path=path, params={
            'name': name,
            'access_code': access_code,
        }, **kwargs).json()

    def history(self, path, **kwargs):
        return self.get('history', path=path, **kwargs).json()

    def mkdir(self, path, force=False, **kwargs):
        try:
            return self.get('fileops/create_folder', params={
                'root': self.root,
                'path': path,
            }, **kwargs).json()
        except errors.FileExistedError:
            if not force:
                raise

    def delete(self, path, to_recycle=None, force=False, **kwargs):
        try:
            return self.get('fileops/delete', params={
                'root': self.root,
                'path': path,
                'to_recycle': to_recycle,
            }, **kwargs)
        except errors.FileNotExistedError:
            if not force:
                raise

    def move(self, from_path, to_path, **kwargs):
        return self.get('fileops/move', params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
        }, **kwargs)

    def copy(self, from_path, to_path, from_copy_ref=None, **kwargs):
        return self.get('fileops/copy', params={
            'root': self.root,
            'from_path': from_path,
            'to_path': to_path,
            'from_copy_ref': from_copy_ref,
        }, **kwargs)

    def copy_ref(self, path, **kwargs):
        return self.get('copy_ref', path=path, **kwargs).json()

    def upload(self, path, data, overwrite=True, source_ip=None, **kwargs):
        """
        :param data: file object or str data.
        """
        host = self.get('fileops/upload_locate', api='CONTENT', params={
            'source_ip': source_ip
        }).json().get('url')
        url = os.path.join(host, str(API_VERSION), 'fileops/upload_file')
        return self.oauth.post(url, params={
            'root': self.root,
            'path': path,
            'overwrite': overwrite,
        }, files=dict(file=data), **kwargs).json()

    def download(self, path, rev=None, **kwargs):
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
        }, stream=True, timeout=kwargs.get('timeout', 1.5), **kwargs)

    def thumbnail(self, width, height, path, **kwargs):
        """
        TYPE_IMG = ('gif', 'png', 'jpg', 'bmp', 'jpeg', 'jpe')
        """
        return self.get('fileops/thumbnail', api='CONV', params={
            'root': self.root,
            'path': path,
            'width': width,
            'height': height,
        }, **kwargs)

    def document_view(self, doc_type, view, path, is_zip=False, **kwargs):
        """
        doc_type = {
            'pdf', 'doc', 'wps', 'csv', 'prn',
            'xls', 'et', 'ppt', 'dps', 'txt', 'rtf'
        }
        view = {'normal', 'android', 'iPad', 'iphone'}
        is_zip = {0, 1}
        """
        return self.get('fileops/documentView', api='CONV', params={
            'root': self.root,
            'path': path,
            'type': doc_type,
            'view': view,
            'zip': 1 if is_zip else 0,
        }, **kwargs)


def load(filename):
    with open(filename, 'rt')as f:
        rs = json.load(f)
        return KuaiPan(
            rs.get('client_key'),
            rs.get('client_secret'),
            rs.get('resource_owner_key'),
            rs.get('resource_owner_secret'),
            rs.get('root'))
