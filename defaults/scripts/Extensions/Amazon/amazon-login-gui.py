#!/usr/bin/env python3
# Amazon Games OAuth login window (GTK + WebKit2).
# 1. `nile auth --login --non-interactive` gives us {url, client_id,
#    code_verifier, serial}
# 2. we show the Amazon login page; after login Amazon redirects to a URL
#    containing openid.oa2.authorization_code
# 3. `nile register --code ... --client-id ... --code-verifier ... --serial ...`
import json
import os
import subprocess
import sys
import urllib.parse

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2

NILE = os.path.expanduser(os.environ.get('NILE', 'nile'))

out = subprocess.run(f"{NILE} auth --login --non-interactive", shell=True,
                     capture_output=True, text=True)
try:
    login_data = json.loads(out.stdout)
except json.JSONDecodeError:
    print(f"nile auth --login failed: {out.stdout} {out.stderr}", file=sys.stderr)
    sys.exit(1)

code = None


def check_uri(uri):
    global code
    if not uri:
        return False
    params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
    if "openid.oa2.authorization_code" in params:
        code = params["openid.oa2.authorization_code"][0]
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


win = Gtk.Window(title="Amazon Games Login")
win.set_default_size(720, 900)
win.connect("destroy", Gtk.main_quit)

webview = WebKit2.WebView()
webview.connect("load-changed", on_load_changed)
webview.connect("decide-policy", on_decide_policy)
webview.load_uri(login_data["url"])

win.add(webview)
win.show_all()
Gtk.main()

if not code:
    print("window closed without a code", file=sys.stderr)
    sys.exit(1)

reg = subprocess.run(
    f"{NILE} register --code '{code}'"
    f" --client-id '{login_data['client_id']}'"
    f" --code-verifier '{login_data['code_verifier']}'"
    f" --serial '{login_data['serial']}'",
    shell=True, capture_output=True, text=True)
print(reg.stdout)
print(reg.stderr, file=sys.stderr)
sys.exit(reg.returncode)
