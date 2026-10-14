#!/usr/bin/env python3
"""Headless EA worker. Private stdin/stdout protocol; never use Helper logging.

The only secret-bearing messages are the initial URL and callback, exchanged
in memory with our parent. Maxima output stays captured, never forwarded.
"""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

import ea
import open_webview
import qrc_callback


def validate_callback(initial_url, uri):
    initial = urlsplit(initial_url)
    if initial.scheme != 'https' or initial.hostname != 'accounts.ea.com':
        raise ValueError('Invalid login origin')
    query = parse_qs(initial.query)
    redirects = query.get('redirect_uri')
    if redirects is None:
        if query.get('client_id') != ['JUNO_PC_CLIENT'] or query.get('response_type') != ['code']:
            raise ValueError('Missing callback destination')
        redirects = ['qrc:///html/login_successful.html']
    if len(redirects) != 1:
        raise ValueError('Missing callback destination')
    expected, actual = urlsplit(redirects[0]), urlsplit(uri)
    if (expected.scheme != 'qrc' or actual.scheme != 'qrc'
            or (actual.netloc, actual.path) != (expected.netloc, expected.path)
            or actual.fragment):
        raise ValueError('Unexpected callback destination')
    qrc_callback.callback_url(uri)
    states = parse_qs(initial.query).get('state')
    if states and parse_qs(actual.query).get('state') != states:
        raise ValueError('Unexpected callback state')


def run():
    cancelled = threading.Event()
    child = [None]
    initial = [None]
    callback_received = threading.Event()
    callback_done = threading.Event()
    output_lock = threading.Lock()

    def emit(kind, **fields):
        with output_lock:
            print(json.dumps({'type': kind, **fields}), flush=True)

    def cancel():
        cancelled.set()
        process = child[0]
        if process is not None and process.poll() is None:
            process.terminate()

    def commands():
        try:
            while not cancelled.is_set():
                line = sys.stdin.readline(65537)
                if not line or len(line) > 65536:
                    cancel()
                    return
                message = json.loads(line)
                if message.get('type') == 'cancel':
                    cancel()
                    return
                if message.get('type') != 'callback' or callback_received.is_set():
                    continue
                uri = message.get('uri', '')
                validate_callback(initial[0] or '', uri)
                # Upstream spawns BROWSER just before binding its listener.
                for attempt in range(20):
                    try:
                        qrc_callback.forward(uri)
                        break
                    except OSError:
                        if cancelled.wait(.1) or attempt == 19:
                            raise
                callback_received.set()
                ea.login_diagnostic('steam-browser-callback', validated=False)
                emit('finishing')
                callback_done.set()
        except Exception:
            ea.login_diagnostic('steam-browser-callback', validated=False,
                                failure_category='callback')
            emit('error', category='callback')
            cancel()

    def interrupted(*_):
        cancel()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    started = time.monotonic()
    try:
        with ea.session_lock(), tempfile.TemporaryDirectory(prefix='skullkey-ea-browser-') as private:
            os.chmod(private, 0o700)
            path = Path(private) / 'browser.sock'
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(str(path))
                os.chmod(path, 0o600)
                listener.listen(1)
                listener.settimeout(.25)

                def receive_url():
                    try:
                        while not cancelled.is_set():
                            try:
                                connection, _ = listener.accept()
                                break
                            except socket.timeout:
                                continue
                        else:
                            return
                        with connection:
                            connection.settimeout(5)
                            chunks = bytearray()
                            while len(chunks) <= 32768:
                                chunk = connection.recv(4096)
                                if not chunk:
                                    break
                                chunks.extend(chunk)
                        uri = chunks.decode()
                        # Reuse exactly the allowlist of our private BROWSER.
                        parsed = urlsplit(uri)
                        if (len(chunks) > 32768 or parsed.scheme != 'https'
                                or parsed.hostname != 'accounts.ea.com'
                                or parsed.username is not None or parsed.password is not None
                                or parsed.port not in (None, 443)):
                            raise ValueError('Invalid login destination')
                        initial[0] = uri
                        emit('url', url=uri)
                    except Exception:
                        if not cancelled.is_set():
                            emit('error', category='browser-transport')
                            cancel()

                environment = ea.env()
                environment['BROWSER'] = str(Path(open_webview.__file__).resolve())
                environment['SK_EA_LOGIN_SOCKET'] = str(path)
                ea.login_diagnostic('steam-browser-cli', validated=False)
                threading.Thread(target=receive_url, daemon=True).start()
                threading.Thread(target=commands, daemon=True).start()
                process = subprocess.Popen([str(ea.client()), 'list-games'], env=environment,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, errors='replace')
                child[0] = process
                if cancelled.is_set():
                    process.terminate()
                output, errors = process.communicate(timeout=600)
                if cancelled.is_set():
                    return 1
                if process.returncode:
                    raise RuntimeError('Library request failed')
                games = ea.parse_library(output + '\n' + errors)
                if initial[0] is not None:
                    callback_done.wait(2)
                    if not callback_received.is_set():
                        raise RuntimeError('Callback not confirmed')
                if not (ea.root() / 'data/maxima/auth.toml').is_file():
                    raise RuntimeError('Session not confirmed')
                state = ea.state()
                state.update(games=games, validated=True)
                ea.save(state)
                ea.login_diagnostic('steam-browser-library', validated=True,
                                    elapsed_seconds=round(time.monotonic() - started, 1))
                cancelled.set()
                emit('done')
                return 0
    except (Exception, KeyboardInterrupt) as error:
        cancel()
        ea.login_diagnostic('steam-browser-login', error, validated=False,
                            elapsed_seconds=round(time.monotonic() - started, 1))
        emit('error', category='login-failed')
        return 1
    finally:
        cancel()
        process = child[0]
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == '__main__':
    try:
        raise SystemExit(run())
    except Exception:
        # Neither exception text nor argv are safe at this boundary.
        print(json.dumps({'type': 'error', 'category': 'worker-start'}), flush=True)
        raise SystemExit(1)
