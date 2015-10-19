twitterprobe
============

Inspired by some investigation of some tweets going (temporarily)
"missing", for example this discussion:

- https://twitter.com/marshray/status/656220752270655489

I hacked together this script that uses txtorcon (and hence Twisted
and txsocksx) to download a public Twitter timeline for a given
username over several different Tor circuits/exit-nodes and then look
for a different list of visible Tweets.

This does *not* use the Twitter API, it is parsing the HTML and
impersonating a Firefox user-agent (probably poorly; just setting
``User-Agent``). Also, it will only see the first 20 tweets in the
timeline.

(So far, I have not seen a different list).

Obviously, this is pretty basic. Also, it inspires me to actually do
something soon about https://github.com/meejah/txtorcon/issues/125

Contributions welcome!


If You Read Only One Thing Read This
------------------------------------

If you're actively twittering while running this, of course you're
going to see the Fearsome Warning that some tweets weren't visible
from some exits.

So, don't do that.


Running It
----------

To run this in a virtualenv, do the following::

    git clone https://github.com/meejah/twitterprobe
    cd twitterprobe
    virtualenv venv
    ./venv/bin/pip install -e .
    twitterprobe --help

Alternatively, install the dependencies "by hand" and simply run
``probe.py``.

This will connect to a locally-running system Tor at the usual
controller address; mess with the call to
``build_local_tor_connection`` if this is not suitable for you. If you
want to follow along with the Tor instance to see what it's doing, I
recommend using ``carml monitor`` from https://github.com/meejah/carml
