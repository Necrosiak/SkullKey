"""SteamOS EA fallback contracts. Fake URLs/processes only; no EA account."""
import ast
import asyncio
import importlib.util
import json
import contextlib
import os
import queue
import tempfile
import threading
from pathlib import Path
import types
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tested_ea_browser', ROOT / 'defaults' / 'scripts' / 'skullkey_ea_browser.py')
browser = importlib.util.module_from_spec(spec)
if importlib.util.find_spec('aiohttp') is None:
    # These unit tests never make HTTP calls. Decky itself already requires
    # aiohttp; don't install it into a user's system Python just for fixtures.
    with patch.dict(sys.modules, {'aiohttp': types.SimpleNamespace(
            WSMsgType=types.SimpleNamespace(TEXT=1))}):
        spec.loader.exec_module(browser)
else:
    spec.loader.exec_module(browser)
INITIAL = 'https://accounts.ea.com/connect/auth?' + urlencode({
    'redirect_uri': 'qrc:///html/login_successful.html', 'state': 'fixture-state'})
CALLBACK = 'qrc:///html/login_successful.html?code=fixture-code&state=fixture-state'


class Input:
    def __init__(self):
        self.messages = []
        self.closed = False

    def write(self, data):
        self.messages.append(json.loads(data))

    async def drain(self):
        pass

    def close(self):
        self.closed = True


class Process:
    def __init__(self):
        self.stdin = Input()
        self.stdout = asyncio.StreamReader()
        self.returncode = None
        self.exited = asyncio.Event()
        self.terminated = False

    def finish(self, code=0):
        self.returncode = code
        self.exited.set()
        self.stdout.feed_eof()

    async def wait(self):
        await self.exited.wait()
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.finish(1)

    def kill(self):
        self.finish(-9)


class ProtocolTests(unittest.TestCase):
    def test_url_and_callback_allowlists(self):
        self.assertTrue(browser.login_url(INITIAL))
        self.assertTrue(browser.callback_matches(INITIAL, CALLBACK))
        for value in ('http://accounts.ea.com/a', 'https://accounts.ea.com.evil.test/a',
                      'https://user@accounts.ea.com/a', 'https://accounts.ea.com:9/a', None):
            self.assertFalse(browser.login_url(value))
        for value in ('qrc:///other?code=x&state=fixture-state',
                      CALLBACK + '&code=second', CALLBACK.replace('fixture-state', 'wrong'),
                      CALLBACK.replace('qrc:', 'https:'), CALLBACK + '#fragment'):
            self.assertFalse(browser.callback_matches(INITIAL, value))

    def test_genuine_no_state_callback_is_supported(self):
        initial = 'https://accounts.ea.com/connect/auth?' + urlencode({
            'redirect_uri': 'qrc:///html/login_successful.html'})
        self.assertTrue(browser.callback_matches(initial, 'qrc:///html/login_successful.html?code=fixture'))

    def test_maxima_registered_redirect_without_explicit_redirect_uri(self):
        initial = 'https://accounts.ea.com/connect/auth?' + urlencode({
            'client_id': 'JUNO_PC_CLIENT', 'response_type': 'code',
            'code_challenge_method': 'S256', 'code_challenge': 'fixture', 'nonce': 'fixture'})
        self.assertTrue(browser.callback_matches(initial, 'qrc:///html/login_successful.html?code=fixture'))
        self.assertFalse(browser.callback_matches(initial.replace('JUNO_PC_CLIENT', 'unrelated'),
                                                  'qrc:///html/login_successful.html?code=fixture'))

    def test_worker_has_no_gui_dependency_or_cli_stdout_forwarding(self):
        text = (ROOT / 'defaults/scripts/Extensions/EA/browser_login.py').read_text()
        tree = ast.parse(text)
        imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
        self.assertNotIn('gi', imports)
        self.assertIn('games = ea.parse_library(output', text)
        self.assertIn("'data/maxima/auth.toml'", text)
        self.assertNotIn('print(output', text)
        self.assertNotIn('print(errors', text)

    def test_existing_store_mapping_is_unchanged_and_ea_is_separate(self):
        tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
        mapping = next(node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'BROWSER_LOGIN'
                               for target in node.targets))
        self.assertEqual(set(ast.literal_eval(mapping.value)), {'Epic', 'GOG', 'Amazon'})
        main = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('platform == "EA"', main)
        self.assertIn('"login-browser"', main)
        self.assertIn('BrowserLogin.ea.abort()', main)

    def test_backend_module_ships_under_scripts(self):
        # A new top-level file can't be written by the self-updater (Decky
        # root-owns the plugin directory): the module lives in scripts/.
        self.assertIn('"scripts", "skullkey_ea_browser.py"', (ROOT / 'main.py').read_text(encoding='utf-8'))
        self.assertTrue((ROOT / 'defaults' / 'scripts' / 'skullkey_ea_browser.py').is_file())


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.login = browser.EASteamBrowser()
        self.login.initial_url = INITIAL
        self.login.process = Process()
        self.login.command = AsyncMock(return_value={})

    def paused(self, url=INITIAL, location=None, session='owned'):
        params = {'requestId': 'fixture-request', 'request': {'url': url}}
        if location is not None:
            params.update(responseStatusCode=302, responseHeaders=[{'name': 'Location', 'value': location}])
        return {'method': 'Fetch.requestPaused', 'sessionId': session, 'params': params}

    async def test_initial_document_is_resumed_and_claims_only_own_session(self):
        await self.login.event(self.paused())
        self.assertEqual(self.login.active_sessions, {'owned'})
        self.login.command.assert_awaited_with('Fetch.continueRequest',
                                              {'requestId': 'fixture-request'}, 'owned')

    async def test_callback_is_forwarded_once_in_private_stdin_not_argv(self):
        self.login.active_sessions.add('owned')
        await asyncio.gather(self.login.event(self.paused(location=CALLBACK)),
                             self.login.event(self.paused(location=CALLBACK)))
        self.assertEqual(self.login.process.stdin.messages, [{'type': 'callback', 'uri': CALLBACK}])
        methods = [call.args[0] for call in self.login.command.await_args_list]
        self.assertEqual(methods.count('Fetch.fulfillRequest'), 1)
        self.assertNotIn('Runtime.evaluate', methods)

    async def test_unowned_ea_tab_cannot_supply_callback(self):
        await self.login.event(self.paused(url='https://accounts.ea.com/unrelated',
                                           location=CALLBACK, session='unowned'))
        self.assertEqual(self.login.process.stdin.messages, [])
        self.login.command.assert_awaited_with('Fetch.continueRequest',
                                              {'requestId': 'fixture-request'}, 'unowned')

    async def test_wrong_callback_state_is_not_forwarded(self):
        self.login.active_sessions.add('owned')
        await self.login.event(self.paused(location=CALLBACK.replace('fixture-state', 'wrong')))
        self.assertEqual(self.login.process.stdin.messages, [])

    async def test_new_page_is_always_resumed_even_if_interception_fails(self):
        self.login.command = AsyncMock(side_effect=[RuntimeError('fixture'), {}])
        await self.login.event({'method': 'Target.attachedToTarget', 'params': {
            'sessionId': 'new', 'targetInfo': {'targetId': 'new-page', 'type': 'page'}}})
        self.assertEqual(self.login.command.await_args_list[-1].args[0], 'Runtime.runIfWaitingForDebugger')
        self.assertEqual(self.login.state['message'], 'ea-browser-interception')
        self.assertTrue(self.login.process.terminated)

    async def test_worker_error_never_reaches_frontend_with_secret_details(self):
        self.login.first = asyncio.get_running_loop().create_future()
        self.login.process.stdout.feed_data((json.dumps({'type': 'error', 'category': CALLBACK}) + '\n').encode())
        await self.login.read_worker()
        self.assertEqual(self.login.state['message'], 'ea-login-failed')
        self.assertEqual((await self.login.first)['error'], 'ea-login-failed')
        self.assertTrue(self.login.process.terminated)

    async def test_existing_authenticated_session_can_finish_without_browser(self):
        self.login.first = asyncio.get_running_loop().create_future()
        self.login.process.stdout.feed_data(b'{"type":"done"}\n')
        self.login.process.finish(0)
        await self.login.read_worker()
        self.assertEqual(self.login.state['status'], 'done')
        self.assertTrue((await self.login.first)['complete'])

    async def test_worker_exit_without_confirmation_is_failure(self):
        self.login.first = asyncio.get_running_loop().create_future()
        self.login.process.finish(0)
        await self.login.read_worker()
        self.assertEqual(self.login.state['message'], 'ea-worker-exited')
        self.assertFalse((await self.login.first)['ok'])

    async def test_cdp_event_does_not_consume_command_reply(self):
        self.login.process = None
        future = asyncio.get_running_loop().create_future()
        self.login.pending[7] = future
        self.login.event = AsyncMock()

        class WS:
            def __aiter__(self):
                self.events = iter([
                    {'method': 'Fetch.requestPaused', 'params': {}},
                    {'id': 7, 'result': {'confirmed': True}}])
                return self

            async def __anext__(self):
                try:
                    event = next(self.events)
                except StopIteration:
                    raise StopAsyncIteration
                return types.SimpleNamespace(type=browser.aiohttp.WSMsgType.TEXT, data=json.dumps(event))

        self.login.ws = WS()
        await self.login.read_cdp()
        self.assertEqual(await future, {'confirmed': True})
        await asyncio.gather(*self.login.handlers)
        self.login.event.assert_awaited_once()

    async def test_plugin_routes_ea_to_private_worker_not_logged_script_helper(self):
        tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
        method = next(node for item in tree.body if isinstance(item, ast.ClassDef)
                      for node in item.body if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == '_browser_login_start')
        worker = types.SimpleNamespace(start=AsyncMock(return_value={'ok': True, 'url': INITIAL}))
        helper = types.SimpleNamespace(
            get_action=lambda *_: {'Command': './scripts/skullkey.sh EA login'},
            get_environment=lambda *_: {'HOME': '/fixture'},
            working_directory='/fixture', call_script=AsyncMock())
        state = types.SimpleNamespace(ea=None, task=None, state={})
        logger = Mock()
        namespace = {'Helper': helper, 'BROWSER_LOGIN': {'Epic': {}, 'GOG': {}, 'Amazon': {}},
                     'BrowserLogin': state, '_ea_browser': types.SimpleNamespace(EASteamBrowser=lambda: worker),
                     'decky_plugin': types.SimpleNamespace(logger=logger)}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<isolated-routing>', 'exec'), namespace)
        result = await namespace['_browser_login_start'](None, 'EALoginActions')
        self.assertTrue(result['ok'])
        helper.call_script.assert_not_awaited()
        self.assertEqual(worker.start.call_args.args[0][-2:], ['EA', 'login-browser'])
        self.assertNotIn(INITIAL, repr(logger.mock_calls))

    async def test_cancel_resolves_pending_start_without_exposing_url(self):
        self.login.first = asyncio.get_running_loop().create_future()
        await self.login.close()
        self.assertEqual(await self.login.first, {'ok': False, 'error': 'ea-login-cancelled'})
        self.assertTrue(self.login.process.terminated)


class StartupFailureTests(unittest.IsolatedAsyncioTestCase):
    async def check_failure(self, endpoint=None, connection_error=False):
        login = browser.EASteamBrowser()
        response = types.SimpleNamespace(raise_for_status=Mock(),
            json=AsyncMock(return_value={'webSocketDebuggerUrl': endpoint}))

        class Request:
            async def __aenter__(self):
                if connection_error:
                    raise OSError('fixture-sensitive-detail')
                return response

            async def __aexit__(self, *args):
                pass

        session = types.SimpleNamespace(get=Mock(return_value=Request()),
            ws_connect=AsyncMock(side_effect=OSError('fixture-sensitive-detail')),
            close=AsyncMock())
        with patch.object(browser.aiohttp, 'ClientTimeout', create=True), \
                patch.object(browser.aiohttp, 'ClientSession', return_value=session, create=True), \
                patch.object(browser.asyncio, 'create_subprocess_exec', new_callable=AsyncMock) as spawn:
            result = await login.start(['fixture-command'], '/fixture', {})
        self.assertEqual(result, {'ok': False, 'error': 'ea-browser-start'})
        self.assertNotIn('fixture-sensitive-detail', repr(result))
        self.assertEqual(login.state['message'], 'ea-browser-start')
        self.assertTrue(login.closed)
        session.close.assert_awaited_once()
        spawn.assert_not_awaited()
        return session

    async def test_cdp_unavailable_is_categorized_not_generic_browser_login_failed(self):
        session = await self.check_failure(connection_error=True)
        session.ws_connect.assert_not_awaited()

    async def test_untrusted_cdp_endpoint_rejected_before_worker(self):
        for endpoint in ('ws://evil.invalid:8080/', 'wss://127.0.0.1:8080/',
                         'ws://127.0.0.1:9999/', 'ws://user@127.0.0.1:8080/'):
            with self.subTest(endpoint=endpoint):
                session = await self.check_failure(endpoint)
                session.ws_connect.assert_not_awaited()

    async def test_cdp_websocket_failure_is_controlled_and_cleaned_up(self):
        session = await self.check_failure('ws://127.0.0.1:8080/devtools/browser/fixture')
        session.ws_connect.assert_awaited_once()


@unittest.skipIf(os.name == 'nt', 'Actual private Unix socket; run on Linux')
class WorkerTests(unittest.TestCase):
    def test_headless_worker_socket_callback_and_library_without_ea_account(self):
        directory = ROOT / 'defaults/scripts/Extensions/EA'
        with patch.object(sys, 'path', [str(directory), *sys.path]):
            worker_spec = importlib.util.spec_from_file_location('headless_worker_fixture', directory / 'browser_login.py')
            worker = importlib.util.module_from_spec(worker_spec)
            worker_spec.loader.exec_module(worker)
        messages, diagnostics, saved = [], [], []
        received = threading.Event()
        input_queue = queue.Queue()

        class In:
            def readline(self, limit):
                return input_queue.get(timeout=8)

        class Out:
            buffer = ''

            def write(self, value):
                self.buffer += value
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if not line:
                        continue
                    message = json.loads(line)
                    messages.append(message)
                    if message['type'] == 'url':
                        input_queue.put(json.dumps({'type': 'callback', 'uri': CALLBACK}) + '\n')

            def flush(self):
                pass

        class FakeCLI:
            returncode = None

            def poll(self):
                return self.returncode

            def terminate(self):
                self.returncode = 1
                received.set()

            def communicate(self, timeout=None):
                # Exercise the real private BROWSER/socket permission checks.
                with patch.dict(os.environ, environment):
                    worker.open_webview.deliver(INITIAL)
                if not received.wait(8):
                    raise AssertionError('Fixture callback not received')
                self.returncode = 0
                return 'Owned games:\nfixture - Fixture game - offer - Installed: false\n', 'private-cli-fixture'

        with tempfile.TemporaryDirectory() as temporary:
            account = Path(temporary)
            def forward(uri):
                worker.validate_callback(INITIAL, uri)
                auth = account / 'data/maxima/auth.toml'
                auth.parent.mkdir(parents=True)
                auth.write_text('fake fixture, not an account')
                received.set()

            def popen(*args, **kwargs):
                nonlocal environment
                environment = kwargs['env']
                return FakeCLI()

            environment = {}
            with patch.object(worker.ea, 'session_lock', contextlib.nullcontext), \
                    patch.object(worker.ea, 'env', return_value={}), \
                    patch.object(worker.ea, 'client', return_value=Path('/fixture/never-executed')), \
                    patch.object(worker.ea, 'root', return_value=account), \
                    patch.object(worker.ea, 'state', return_value={}), \
                    patch.object(worker.ea, 'save', side_effect=saved.append), \
                    patch.object(worker.ea, 'login_diagnostic', side_effect=lambda *a, **k: diagnostics.append((a, k))), \
                    patch.object(worker.subprocess, 'Popen', side_effect=popen), \
                    patch.object(worker.qrc_callback, 'forward', side_effect=forward), \
                    patch.object(worker.signal, 'signal'), \
                    patch.object(worker.sys, 'stdin', In()), patch.object(worker.sys, 'stdout', Out()):
                result = worker.run()
            input_queue.put('')
            self.assertEqual(result, 0)
            self.assertTrue(saved[0]['validated'])
            self.assertIn('done', [message['type'] for message in messages])
            self.assertNotIn('private-cli-fixture', json.dumps(messages) + repr(diagnostics))

    def test_worker_rejects_wrong_callback_destination_before_forwarding(self):
        directory = ROOT / 'defaults/scripts/Extensions/EA'
        with patch.object(sys, 'path', [str(directory), *sys.path]):
            worker_spec = importlib.util.spec_from_file_location('worker_validation_fixture', directory / 'browser_login.py')
            worker = importlib.util.module_from_spec(worker_spec)
            worker_spec.loader.exec_module(worker)
        for uri in (CALLBACK + '&code=second', CALLBACK.replace('fixture-state', 'wrong'),
                    'qrc:///other?code=fixture', 'https://evil.test/?code=fixture'):
            with self.assertRaises(ValueError):
                worker.validate_callback(INITIAL, uri)
        initial = 'https://accounts.ea.com/connect/auth?client_id=JUNO_PC_CLIENT&response_type=code'
        worker.validate_callback(initial, 'qrc:///html/login_successful.html?code=fixture')


if __name__ == '__main__':
    unittest.main()
