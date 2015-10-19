from __future__ import print_function

import random

import click

from twisted.internet.defer import inlineCallbacks, Deferred, DeferredList, returnValue
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.task import react, deferLater
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.web import client
from twisted.web.http_headers import Headers

from zope.interface import implementer

import txtorcon
import txsocksx
from txsocksx.http import SOCKS5Agent

from lxml import html


def sleep(reactor, delay):
    return deferLater(reactor, delay, lambda: None)

def tweets_in_timeline(data):
    elements = html.fromstring(data)
    return [t.get('data-tweet-id') for t in elements.find_class('tweet') if t.get('data-tweet-id')]


class CircuitBuilder(txtorcon.CircuitListenerMixin):

    def __init__(self, state, verbose):
        self.state = state
        self._created_circuits = []
        self._exits_pending = []
        self._waiting = []
        self._verbose = verbose

    # ICircuitListener API
    def circuit_built(self, circuit):
        "ICircuitListener"
        if circuit.purpose != 'GENERAL':
            return
        self._created_circuits.append(circuit)

    def circuit_failed(self, circuit, **kw):
        if circuit in self._waiting:
            # print("A circuit '{}' we requested failed '{}'".format(circuit.id, kw['REASON']))
            # FIXME why isn't is_built doing errback itself?!
            circuit.is_built.errback(Exception(kw['REASON']))

    @inlineCallbacks
    def create_circuit(self, reactor):
        """
        returns a Deferred that callbacks when we've successfully created
        a circuit -- will retry on failures.
        """

        while True:
            try:
                # print("building circuit")
                circ = yield self._create_circuit(reactor)
                self._waiting.append(circ)
                # print("DING", str(circ))
                yield circ.is_built
                if self._verbose:
                    print("built circuit {}: {}".format(
                        circ.id,
                        '>'.join([x.location.countrycode for x in circ.path]),
                    ))
                break

            except Exception as e:
                print("Failed to build circuit '{}'; retrying in 1s.".format(e))
                yield sleep(reactor, 1)
                continue
        returnValue(circ)

    def _create_circuit(self, reactor):
        # we don't want to create a new circuit which exits through a
        # country we've already exited from.
        exit_countries = [x.location.countrycode for x in self._exits_pending]
        last = filter(
            lambda x: x.location.countrycode not in exit_countries,
            self.state.routers.values()
        )
        exit_node = random.choice(last)
        self._exits_pending.append(exit_node)
        path = [random.choice(self.state.entry_guards.values()),
                random.choice(self.state.routers.values()),
                exit_node]

        path_str = '->'.join([r.location.countrycode for r in path])
        # print("  requesting a circuit:", path_str)

        def remove_exit(f):
            self._exits_pending.remove(exit_node)
            return f
        d = self.state.build_circuit(path)
        d.addErrback(remove_exit)
        return d



@implementer(IStreamClientEndpoint)
class TorCircuitEndpoint(object):
    def __init__(self, reactor, wrapped_endpoint, builder, attacher):
        self._reactor = reactor
        self._wrapped = wrapped_endpoint
        self._builder = builder
        self._attacher = attacher

        self.stream = None

    @inlineCallbacks
    def connect(self, protocolfactory):
        # print("creating circuit")
        circ = yield self._builder.create_circuit(self._reactor)
        # print("built circuit:", circ.id, '>'.join([x.location.countrycode for x in circ.path]))
        proto = yield self._wrapped.connect(protocolfactory)
        # print("BLAMMO", proto, proto.transport, proto.transport.getHost())
        port = proto.transport.getHost().port
        # print("my port", port)
        self.stream = yield self._attacher.circuit_for(port, circ)
        # print("discovered our port", port)
        # print("...and stream", self.stream, self.stream.circuit)
        returnValue(proto)


@implementer(txtorcon.IStreamAttacher)
class AttachBySourcePort(txtorcon.StreamListenerMixin):
    def __init__(self, verbose):
        self._port_to_circuit = dict()
        self._verbose = verbose

    def circuit_for(self, port, circuit):
        d = Deferred()
        self._port_to_circuit[port] = (circuit, d)
        return d

    # IStreamListener API
    def stream_attach(self, stream, circuit):
        if self._verbose:
            print("stream", stream.id, " attached to circuit", circuit.id, end='')
            print(": ", '>'.join([x.location.countrycode for x in circuit.path]))

    # IStreamAttacher API
    def attach_stream(self, stream, circuits):
        """
        IStreamAttacher API

        What we do here is create a new circuit for every stream we
        want to attach.
        """

        # print("attach_stream", stream.id, stream.source_port)
        if stream.source_port in self._port_to_circuit:
            (circ, d) = self._port_to_circuit[stream.source_port]
            # print("found circ", circ)
            d.callback(stream)
#            def attach_to(_):
#                print("ATTACHING", circ)
#                return circ
#            circ.is_built.addCallback(attach_to)
            return circ.is_built

        print("RETURNING NONE")
        # we don't care; let Tor do whatever it wants
        return None


class TwitterProbe(object):
    """
    This creates 10 random circuits, and downloads a given user's
    Twitter timeline over each circuit (in parallel).

    Then end result is a mapping of exit-node -> tweet-IDs
    """

    def __init__(self, state, builder, attacher, results, verbose):
        self.state = state
        self.builder = builder
        self.attacher = attacher
        self.results = results  # might be None (or an open file-like)

        self._verbose = verbose
        # we're interested in which results came via which circuit
        self._circuit_to_results = dict()

        if self.results:
            self.results.write('exit-id, country-code, tweet-IDs\n')
            self.results.flush()

    @inlineCallbacks
    def tweets_from(self, reactor, username):
        tor_ep = TorCircuitEndpoint(reactor, TCP4ClientEndpoint(reactor, '127.0.0.1', 9050), self.builder, self.attacher)
        agent = SOCKS5Agent(reactor, proxyEndpoint=tor_ep)
        headers = Headers()
        headers.addRawHeader(
            b"User-Agent",
            b"Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1"
        )
        # print("XXXX", agent._wrappedAgent)
        result = None
        while result is None:
            try:
                result = yield agent.request('GET', 'https://twitter.com/{}'.format(username), headers=headers)
            except Exception as e:
                if self._verbose:
                    print("GET failed because '{}'; trying again.".format(e))
                continue

        # print("connected", result)
        stream = tor_ep.stream
        # print("stream for this one", stream, stream.circuit)
        body = yield client.readBody(result)
        # print("body contains {} bytes".format(len(body)))
        tweets = tweets_in_timeline(body)

        print("Circuit {} ({}): {} tweets, {} bytes of HTML".format(
            stream.circuit.id,
            '>'.join([x.location.countrycode for x in stream.circuit.path]),
            len(tweets),
            len(body),
        ))
        if self._verbose:
            print("  {}".format(' '.join(tweets)))

        self._circuit_to_results[stream.circuit] = tweets
        if self.results:
            exit_node = stream.circuit.path[-1]
            self.results.write(
                '{}, {}, {}'.format(
                    exit_node.id_hex,
                    exit_node.location.countrycode,
                    ' '.join(tweets),
                )
            )
            self.results.flush()

        if self._verbose:
            print("  (completed {} feeds).".format(len(self._circuit_to_results)))
        returnValue(tweets)


@inlineCallbacks
def main(reactor, username, num_probes, results, verbose):
    state = yield txtorcon.build_local_tor_connection(reactor)
    if verbose:
        print("Connected to a Tor version", state.protocol.version)

    builder = CircuitBuilder(state, verbose)
    yield state.add_circuit_listener(builder)

    attacher = AttachBySourcePort(verbose)
    yield state.set_attacher(attacher, reactor)
    yield state.add_stream_listener(attacher)

    probe = TwitterProbe(state, builder, attacher, results, verbose)

    timeline_downloads = []
    for x in range(num_probes):
        d = probe.tweets_from(reactor, username)
        timeline_downloads.append(d)
    results = yield DeferredList(timeline_downloads)

    print("Downloads concluded. A Fearsome Warning will be printed below if we detect discrepancies.")
    print("Results:\n\n")
    common = None
    for (circ, tweets) in probe._circuit_to_results.iteritems():
        if common is None:
            common = set(tweets)
        else:
            common = set(tweets).intersection(common)

    print('"ID of Tor exit router used", "country code", "tweet IDs (space-delimited)"')
    print()
    for (circ, tweets) in probe._circuit_to_results.iteritems():
        exit_node = circ.path[-1]
        print("{0}, {1}, {2}".format(exit_node.id_hex, exit_node.location.countrycode, ' '.join(tweets)))
        if set(tweets) != common:
            missing = set(tweets).difference(common)
            print("  *Fearsome Warning*: missing tweets: {}".format(
                ' '.join(missing),
            ))


@click.command()
@click.option(
    '--user', required=True,
    help="Twitter username (e.g. 'meejah')",
)
@click.option(
    '--probes', default=10,
    help='Number of concurrent circuits to use (1 feed per circuit).',
)
@click.option(
    '--results', default=None,
    type=click.File('wb'),
)
@click.option(
    'verbose',
    '--verbose/--quiet', default=True, is_flag=True,
)
def cli(user, probes, results, verbose):
    if False:
        # writes a 'txtorcon.log' with debugging information
        from txtorcon.log import debug_logging
        debug_logging()

    args = (user, probes, results, verbose)
    react(main, args)


if __name__ == '__main__':
    cli()
