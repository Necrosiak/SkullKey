#!/usr/bin/env python3
# OAuth login window shared by GOG and Epic (GTK + WebKit2).  GOG returns its
# code in the redirect URL.  Epic's legendary.gl helper renders a JSON response
# containing authorizationCode; --epic reads that value from the finished page.
# Exit 1 = window closed without logging in.
import json
import sys
import urllib.parse

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2

GALAXY_CLIENT_ID = "46899977096215655"
REDIRECT = "https://embed.gog.com/on_login_success?origin=client"
GOG_LOGIN_URL = (
    "https://auth.gog.com/auth?client_id=" + GALAXY_CLIENT_ID
    + "&redirect_uri=" + urllib.parse.quote(REDIRECT, safe="")
    + "&response_type=code&layout=galaxy"
)

epic_mode = "--epic" in sys.argv[1:]
login_url = "https://legendary.gl/epiclogin" if epic_mode else GOG_LOGIN_URL
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


def on_epic_javascript_finished(webview, result, _data):
    global code
    try:
        js_result = webview.run_javascript_finish(result)
        body = js_result.get_js_value().to_string()
        payload = json.loads(body)
        value = payload.get("authorizationCode")
        if value:
            code = value
            Gtk.main_quit()
    except Exception as exc:
        print(f"Could not read Epic authorization response: {exc}", file=sys.stderr)


def on_load_changed(webview, event):
    if epic_mode:
        if event == WebKit2.LoadEvent.FINISHED:
            webview.run_javascript("document.body.innerText", None,
                                   on_epic_javascript_finished, None)
    else:
        check_uri(webview.get_uri())


def on_decide_policy(webview, decision, decision_type):
    if decision_type in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                         WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
        try:
            uri = decision.get_navigation_action().get_request().get_uri()
        except Exception:
            return False
        if not epic_mode and check_uri(uri):
            decision.ignore()
            return True
    return False


win = Gtk.Window(title="Epic Games Login" if epic_mode else "GOG Login")
win.set_default_size(720, 900)
win.connect("destroy", Gtk.main_quit)

webview = WebKit2.WebView()
webview.connect("load-changed", on_load_changed)
webview.connect("decide-policy", on_decide_policy)
webview.load_uri(login_url)

win.add(webview)
win.show_all()
Gtk.main()

if code:
    print(code)
    sys.exit(0)
sys.exit(1)
