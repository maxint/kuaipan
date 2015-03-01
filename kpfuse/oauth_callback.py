# coding: utf-8

import BaseHTTPServer
import urlparse


def http_authorise(url, oauth_key='oauth_verifier', port=8888):
    import webbrowser

    webbrowser.open(url)

    class ProxyClass:
        code = None
        key = oauth_key

        def __init__(self):
            pass

        class ServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
            def echo_html(self, content):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(content)
                self.wfile.close()

            def do_GET(self):
                qs = urlparse.parse_qs(urlparse.urlsplit(self.path).query)
                if ProxyClass.key in qs:
                    ProxyClass.code = qs[ProxyClass.key][0]
                    self.echo_html('''<html>
    <head>
    <meta charset="utf-8"/>
    <title>OK</title>
    </head>
    <body>Succeed.</body>
    </html> ''')

    httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', port), ProxyClass.ServerRequestHandler)
    httpd.handle_request()
    while ProxyClass.code is None:
        pass
    httpd.server_close()

    return ProxyClass.code