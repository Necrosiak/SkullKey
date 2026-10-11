#!/usr/bin/env python3
"""Game Mode EA sign-in, like GOG/Epic. No DOM/credential inspection or logs."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

import ea
import qrc_callback


def run():
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk, WebKit2, GLib

    cancelled = threading.Event()
    child = [None]
    callback_sent = [False]
    success = [False]
    window = Gtk.Window(title="SkullKey — EA / Maxima")
    window.set_default_size(960, 720)
    window.maximize()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    status = Gtk.Label(label="Préparation de la connexion EA…")
    status.set_margin_top(10)
    status.set_margin_bottom(10)
    box.pack_start(status, False, False, 0)
    # Do not reuse Firefox's profile, extensions or cookies; no persistent
    # browser credential store is created by this login window.
    context = WebKit2.WebContext.new_ephemeral()
    view = WebKit2.WebView.new_with_context(context)
    box.pack_start(view, True, True, 0)
    window.add(box)

    def stop(*_):
        cancelled.set()
        process = child[0]
        if process is not None and process.poll() is None:
            process.terminate()  # Only this window's own Maxima child.
        Gtk.main_quit()

    window.connect("destroy", stop)

    def finish(ok):
        if cancelled.is_set():
            return False
        success[0] = ok
        if ok:
            Gtk.main_quit()
        else:
            status.set_text("Connexion non confirmée. Fermez cette fenêtre puis réessayez dans SkullKey.")
        return False

    def forward(uri):
        # Secret callback stays in memory and goes directly to Maxima's fixed
        # loopback listener; Steam never tries to navigate to qrc://.
        try:
            qrc_callback.forward(uri)
            ea.login_diagnostic("embedded-callback-received", validated=False)
            GLib.idle_add(status.set_text, "Connexion reçue — récupération de la bibliothèque EA…")
        except Exception as error:
            ea.login_diagnostic("embedded-callback", error, validated=False)
            GLib.idle_add(finish, False)

    def policy(webview, decision, kind):
        if kind not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                        WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
            return False
        uri = decision.get_navigation_action().get_request().get_uri()
        parsed = urlsplit(uri)
        if parsed.scheme == "qrc":
            decision.ignore()
            try:
                qrc_callback.callback_url(uri)
            except ValueError:
                return True
            if not callback_sent[0]:
                callback_sent[0] = True
                threading.Thread(target=forward, args=(uri,), daemon=True).start()
            return True
        if parsed.scheme not in ("https", "about"):
            decision.ignore()
            return True
        if kind == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
            decision.ignore()
            webview.load_uri(uri)
            return True
        return False

    view.connect("decide-policy", policy)

    def failed_load(_view, _event, _uri, _error):
        # The URI/error can contain OAuth data: never print or persist it.
        status.set_text("La page EA n’a pas pu charger. Fermez la fenêtre puis réessayez.")
        return True

    view.connect("load-failed", failed_load)

    with tempfile.TemporaryDirectory(prefix="skullkey-ea-login-") as private:
        os.chmod(private, 0o700)
        path = Path(private) / "browser.sock"
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(path))
            os.chmod(path, 0o600)
            listener.listen(1)
            listener.settimeout(1)

            def receive_url():
                while not cancelled.is_set():
                    try:
                        connection, _ = listener.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        return
                    with connection:
                        connection.settimeout(10)
                        data = bytearray()
                        while len(data) <= 32768:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            data.extend(chunk)
                    if cancelled.is_set() or len(data) > 32768:
                        return
                    uri = data.decode()
                    parsed = urlsplit(uri)
                    if parsed.scheme != "https" or parsed.hostname != "accounts.ea.com":
                        GLib.idle_add(finish, False)
                        return
                    GLib.idle_add(status.set_text, "Connectez-vous à EA dans cette fenêtre.")
                    GLib.idle_add(view.load_uri, uri)
                    return

            def authenticate():
                started = time.monotonic()
                try:
                    with ea.session_lock():
                        environment = ea.env()
                        environment["BROWSER"] = str(Path(__file__).with_name("open_webview.py").resolve())
                        environment["SK_EA_LOGIN_SOCKET"] = str(path)
                        ea.login_diagnostic("embedded-cli-start", validated=False)
                        process = subprocess.Popen([str(ea.client()), "list-games"], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        child[0] = process
                        if cancelled.is_set():
                            process.terminate()
                        output, errors = process.communicate(timeout=600)
                        if cancelled.is_set():
                            return
                        metadata = dict(exit_code=process.returncode,
                                        elapsed_seconds=round(time.monotonic() - started, 1))
                        if process.returncode:
                            ea.login_diagnostic("embedded-list-games", validated=False, **metadata)
                            GLib.idle_add(finish, False)
                            return
                        games = ea.parse_library(output + "\n" + errors)
                        state = ea.state()
                        state.update(games=games, validated=True)
                        ea.save(state)
                        ea.login_diagnostic("embedded-list-games", validated=True, **metadata)
                        GLib.idle_add(finish, True)
                except Exception as error:
                    process = child[0]
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.communicate()
                    ea.login_diagnostic("embedded-login", error, validated=False,
                                        elapsed_seconds=round(time.monotonic() - started, 1))
                    GLib.idle_add(finish, False)

            threading.Thread(target=receive_url, daemon=True).start()
            threading.Thread(target=authenticate, daemon=True).start()
            window.show_all()
            Gtk.main()
            cancelled.set()
            process = child[0]
            if process is not None and process.poll() is None:
                process.terminate()
    return 0 if success[0] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as error:
        try:
            ea.login_diagnostic("embedded-window", error, validated=False)
        except Exception:
            pass
        raise SystemExit(1)
