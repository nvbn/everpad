import sys
sys.path.append('..')
sys.path.append('../..')
from everpad.const import CONSUMER_KEY, CONSUMER_SECRET, HOST
from everpad.tools import provider
import web
import argparse
import everpad.monkey
import oauth2 as oauth
import urlparse

urls = (
    '/', 'Auth',
)


class Auth(object):
    def GET(self):
        return 'Authorisation success!'


app = web.application(urls, globals())

argv = sys.argv[1:]
def my_processor(handler): 
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--token', type=str, help='oauth token')
        parser.add_argument('--secret', type=str, help='oauth secret')
        args = parser.parse_args(argv)
        verifier = web.input()['oauth_verifier']
        token = oauth.Token(args.token, args.secret)
        token.set_verifier(verifier)
        consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
        client = oauth.Client(consumer, token)
        resp, content = client.request('https://%s/oauth' % HOST, 'POST')
        access_token = dict(urlparse.parse_qsl(content))
        provider.authenticate(access_token['oauth_token'])
    except KeyError:
        pass
    return handler() 

app.add_processor(my_processor)


if __name__ == '__main__':
    sys.argv[1:] = ['15216']
    app.run()
