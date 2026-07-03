#!/usr/bin/env python3
# GOG OAuth login window (GTK + WebKit2, both shipped with Bazzite/SteamOS-like
# systems). Shows the GOG login page; when GOG redirects to
# embed.gog.com/on_login_success?code=XXX we grab the code, print it on stdout
# and exit 0. Exit 1 = window closed without logging in.
import sys
import urllib.parse

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2

GALAXY_CLIENT_ID = "46899977096215655"
REDIRECT = "https://embed.gog.com/on_login_success?origin=client"
LOGIN_URL = (
    "https://auth.gog.com/auth?client_id=" + GALAXY_CLIENT_ID
    + "&redirect_uri=" + urllib.parse.quote(REDIRECT, safe="")
    + "&response_type=code&layout=galaxy"
)

code = None


def check_uri(uri):
    global code
    if uri and uri.startswith("https://embed.gog.com/on_login_success"):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
        if "code" in params:
            code = params["code"][0]
            Gtk.main_quit()
            return True
    return False


def on_load_changed(webview, event):
    check_uri(webview.get_uri())


def on_decide_policy(webview, decision, decision_type):
    if decision_type in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                         WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
        try:
            uri = decision.get_navigation_action().get_request().get_uri()
        except Exception:
            return False
        if check_uri(uri):
            decision.ignore()
            return True
    return False


win = Gtk.Window(title="GOG Login")
win.set_default_size(720, 900)
win.connect("destroy", Gtk.main_quit)

webview = WebKit2.WebView()
webview.connect("load-changed", on_load_changed)
webview.connect("decide-policy", on_decide_policy)
webview.load_uri(LOGIN_URL)

win.add(webview)
win.show_all()
Gtk.main()

if code:
    print(code)
    sys.exit(0)
sys.exit(1)
