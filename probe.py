
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.task import react
from twisted.web import client
from twisted.web.http_headers import Headers

import txtorcon
import txsocksx
from txsocksx.http import SOCKS5Agent

from lxml import html


def tweets_in_timeline(data):
    elements = html.fromstring(data)
    return [t.get('data-tweet-id') for t in elements.find_class('tweet') if t.get('data-tweet-id')]


@inlineCallbacks
def main(reactor):
    tor_ep = TCP4ClientEndpoint(reactor, '127.0.0.1', 9050)
    agent = SOCKS5Agent(reactor, proxyEndpoint=tor_ep)
    headers = Headers()
    headers.addRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1")
    res = yield agent.request('GET', 'https://twitter.com/meejah', headers=headers)
    print("RESULT", res)
    print(dir(res))
    body = yield client.readBody(res)
    print("body contains {} bytes".format(len(body)))
    tweets = tweets_in_timeline(data)
    print("tweets:", tweets)


if __name__ == '__main__':
    #react(main)
    print(tweets_in_timeline(open('foo.html', 'rb').read()))
