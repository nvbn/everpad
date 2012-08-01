'''
Replacement of HTTPS client from standart httplib module

workaround of ssl bug: https://bugs.launchpad.net/ubuntu/source/openssl/bug/965371
Copyright (C) http://docs.python.org/license.html

Marat Khayrullin <xmm.dev@gmail.com>
'''

import httplib
import socket
try:
    import ssl
except ImportError:
    pass
else:

    class HTTPSConnection(httplib.HTTPConnection):
        "This class allows communication via SSL."

        default_port = httplib.HTTPS_PORT

        def __init__(self, host, port=None, key_file=None, cert_file=None,
                     strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                     source_address=None):
            httplib.HTTPConnection.__init__(self, host, port, strict, timeout,
                                    source_address)
            self.key_file = key_file
            self.cert_file = cert_file

        def connect(self):
            "Connect to a host on a given (SSL) port."

            sock = socket.create_connection((self.host, self.port),
                                            self.timeout, self.source_address)
            if self._tunnel_host:
                self.sock = sock
                self._tunnel()
            self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)

    #__all__.append("HTTPSConnection")

    class HTTPS(httplib.HTTP):
        """Compatibility with 1.5 httplib interface

        Python 1.5.2 did not have an HTTPS class, but it defined an
        interface for sending http requests that is also useful for
        https.
        """

        _connection_class = HTTPSConnection

        def __init__(self, host='', port=None, key_file=None, cert_file=None,
                     strict=None):
            # provide a default host, pass the X509 cert info

            # urf. compensate for bad input.
            if port == 0:
                port = None
            self._setup(self._connection_class(host, port, key_file,
                                               cert_file, strict))

            # we never actually use these for anything, but we keep them
            # here for compatibility with post-1.5.2 CVS.
            self.key_file = key_file
            self.cert_file = cert_file
