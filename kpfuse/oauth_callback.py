# coding: utf-8

import BaseHTTPServer
import urlparse


def http_authorise(url, oauth_key='oauth_verifier', port=8888):
    import webbrowser

    webbrowser.open(url)

    code = None

    class ServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
        def echo_html(self, content):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(content)
            self.wfile.close()

        def do_GET(self):
            qs = urlparse.parse_qs(urlparse.urlsplit(self.path).query)
            global oauth_key
            if oauth_key in qs:
                global code
                code = qs[oauth_key][0]
                self.echo_html('''<html>
    <head>
    <meta charset="utf-8"/>
    <title>OK</title>
    </head>
    <body>Succeed.</body>
    </html> ''')

    httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', port), ServerRequestHandler)
    httpd.handle_request()
    while code is None:
        pass
    httpd.server_close()

    return code