#!/usr/bin/env python3
"""Forward an EA qrc callback to Maxima's loopback listener; never log it."""
import sys
import http.client
import urllib.parse
import urllib.request


def callback_url(uri):
    parsed = urllib.parse.urlsplit(uri)
    query = urllib.parse.parse_qs(parsed.query)
    if parsed.scheme != "qrc" or len(query.get("code", [])) != 1:
        raise ValueError("Invalid OAuth callback")
    code = query["code"][0]
    if not code or len(code) > 4096:
        raise ValueError("Invalid code")
    return "http://127.0.0.1:31033/auth?" + urllib.parse.urlencode({"code": code})


def forward(uri):
    url = callback_url(uri)
    try:
        urllib.request.urlopen(url, timeout=10).close()
    except http.client.RemoteDisconnected:
        # Maxima consumes the request, then deliberately closes without
        # writing an HTTP response. That is not a rejected OAuth callback.
        pass


if __name__ == "__main__":
    try:
        # Upstream closes the socket after consuming the request, sometimes
        # without an HTTP response. Never print the URL or authorization code.
        forward(sys.argv[1])
    except Exception:
        sys.exit(1)
