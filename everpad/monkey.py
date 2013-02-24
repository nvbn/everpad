import httplib2
import ssl


def _ssl_wrap_socket(sock, key_file, cert_file,
                         disable_validation, ca_certs):
    if disable_validation:
        cert_reqs = ssl.CERT_NONE
    else:
        cert_reqs = ssl.CERT_REQUIRED
    # We should be specifying SSL version 3 or TLS v1, but the ssl module
    # doesn't expose the necessary knobs. So we need to go with the default
    # of SSLv23.
    return ssl.wrap_socket(sock, keyfile=key_file, certfile=cert_file,
        cert_reqs=cert_reqs, ca_certs=ca_certs, ssl_version=ssl.PROTOCOL_TLSv1)
httplib2._ssl_wrap_socket = _ssl_wrap_socket
