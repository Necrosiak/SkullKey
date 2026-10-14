"""EA login through Steam's browser, without GTK or credential/DOM inspection.

Use a dedicated CDP connection: command replies and events must not consume
each other. Intercept the owned EA redirect before Steam navigates to qrc:.
All OAuth data stays in memory and private subprocess pipes, never logs/argv.
"""
import asyncio
import base64
import json
from urllib.parse import parse_qs, urlsplit

import aiohttp


def login_url(value):
    if not isinstance(value, str) or len(value.encode()) > 32768:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname == 'accounts.ea.com'
                and url.port in (None, 443) and url.username is None and url.password is None)
    except ValueError:
        return False


def callback_matches(initial, uri):
    if not login_url(initial) or not isinstance(uri, str) or len(uri) > 8192:
        return False
    try:
        query = parse_qs(urlsplit(initial).query)
        destinations = query.get('redirect_uri')
        # Maxima 0.14.3 omits redirect_uri: EA registers this qrc destination
        # for JUNO_PC_CLIENT (also documented by its maxima-qrc-handler.sh).
        if destinations is None:
            if query.get('client_id') != ['JUNO_PC_CLIENT'] or query.get('response_type') != ['code']:
                return False
            destinations = ['qrc:///html/login_successful.html']
        if len(destinations) != 1:
            return False
        expected, actual = urlsplit(destinations[0]), urlsplit(uri)
        values = parse_qs(actual.query)
        codes = values.get('code', [])
        return (expected.scheme == actual.scheme == 'qrc'
                and (expected.netloc, expected.path) == (actual.netloc, actual.path)
                and not actual.fragment and len(codes) == 1 and 0 < len(codes[0]) <= 4096
                and (not query.get('state') or values.get('state') == query['state']))
    except ValueError:
        return False


class EASteamBrowser:
    def __init__(self):
        self.state = {'status': 'waiting', 'platform': 'EA'}
        self.process = None
        self.ws = None
        self.http = None
        self.reader = None
        self.monitor = None
        self.handlers = set()
        self.pending = {}
        self.sessions = set()
        self.targets = set()
        self.active_sessions = set()
        self.sequence = 0
        self.initial_url = None
        self.callback_sent = False
        self.first = None
        self.closed = False

    async def command(self, method, params=None, session=None):
        self.sequence += 1
        identifier = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        message = {'id': identifier, 'method': method, 'params': params or {}}
        if session:
            message['sessionId'] = session
        try:
            await self.ws.send_json(message)
            return await asyncio.wait_for(future, 5)
        finally:
            self.pending.pop(identifier, None)

    def fail(self, category):
        if self.closed:
            return
        self.state = {'status': 'error', 'platform': 'EA', 'message': category}
        if self.first is not None and not self.first.done():
            self.first.set_result({'ok': False, 'error': category})
        self.abort()

    def abort(self):
        # Synchronous, including during Decky unload. EOF cancels the worker,
        # whose own finally block terminates only its Maxima child.
        if self.process is not None and self.process.returncode is None:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass

    async def start(self, command, cwd, environment):
        self.first = asyncio.get_running_loop().create_future()
        try:
            self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            async with self.http.get('http://127.0.0.1:8080/json/version', allow_redirects=False) as response:
                response.raise_for_status()
                version = await response.json(content_type=None)
            endpoint = urlsplit(version['webSocketDebuggerUrl'])
            if (endpoint.scheme != 'ws' or endpoint.hostname not in ('127.0.0.1', 'localhost')
                    or endpoint.port != 8080 or endpoint.username is not None
                    or endpoint.password is not None):
                raise ValueError('Invalid local CDP endpoint')
            self.ws = await self.http.ws_connect(version['webSocketDebuggerUrl'], max_msg_size=1048576)
            self.reader = asyncio.create_task(self.read_cdp())
            await self.command('Target.setAutoAttach', {'autoAttach': True, 'flatten': True,
                               'waitForDebuggerOnStart': True,
                               'filter': [{'type': 'page'}, {'exclude': True}]})
            targets = (await self.command('Target.getTargets')).get('targetInfos', [])
            for target in targets:
                if target.get('type') == 'page' and target['targetId'] not in self.targets:
                    attached = await self.command('Target.attachToTarget',
                                                  {'targetId': target['targetId'], 'flatten': True})
                    await self.attach(attached['sessionId'], target)
            # Install interception before returning the URL to the frontend,
            # including for a reused Steam browser and an already signed-in EA.
            if self.handlers:
                await asyncio.gather(*tuple(self.handlers))
            self.process = await asyncio.create_subprocess_exec(
                *command, cwd=cwd, env=environment, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                limit=65536, start_new_session=True)
            self.monitor = asyncio.create_task(self.read_worker())
            return await asyncio.wait_for(asyncio.shield(self.first), 90)
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception:
            self.fail('ea-browser-start')
            await self.close()
            return {'ok': False, 'error': 'ea-browser-start'}

    async def read_cdp(self):
        try:
            async for message in self.ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    break
                data = json.loads(message.data)
                if 'id' in data:
                    future = self.pending.get(data['id'])
                    if future is not None and not future.done():
                        if 'error' in data:
                            future.set_exception(RuntimeError('CDP command failed'))
                        else:
                            future.set_result(data.get('result') or {})
                elif data.get('method') in ('Target.attachedToTarget', 'Fetch.requestPaused'):
                    task = asyncio.create_task(self.event(data))
                    self.handlers.add(task)
                    task.add_done_callback(self.handlers.discard)
            if not self.closed and self.state['status'] not in ('done', 'error'):
                self.fail('ea-browser-connection')
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.closed:
                self.fail('ea-browser-connection')
        finally:
            for future in tuple(self.pending.values()):
                if not future.done():
                    future.set_exception(RuntimeError('CDP closed'))

    async def attach(self, session, target):
        if session in self.sessions:
            return
        self.sessions.add(session)
        self.targets.add(target['targetId'])
        try:
            # Only EA document requests; no page bodies, form fields, cookie
            # stores or other sites are read. Other requests immediately resume.
            patterns = [{'urlPattern': 'https://' + host + '/*',
                         'resourceType': 'Document', 'requestStage': stage}
                        for host in ('accounts.ea.com', 'signin.ea.com')
                        for stage in ('Request', 'Response')]
            await self.command('Fetch.enable', {'patterns': patterns}, session)
        finally:
            await self.command('Runtime.runIfWaitingForDebugger', session=session)

    async def event(self, data):
        try:
            params = data.get('params') or {}
            if data['method'] == 'Target.attachedToTarget':
                await self.attach(params['sessionId'], params['targetInfo'])
                return
            session = data.get('sessionId')
            identifier = params['requestId']
            request_url = (params.get('request') or {}).get('url')
            if self.initial_url and request_url == self.initial_url:
                self.active_sessions.add(session)
            locations = [header.get('value', '') for header in params.get('responseHeaders', [])
                         if header.get('name', '').lower() == 'location']
            if (session in self.active_sessions and not self.callback_sent and len(locations) == 1
                    and 300 <= params.get('responseStatusCode', 0) < 400
                    and callback_matches(self.initial_url, locations[0])):
                # A harmless response stops qrc navigation in Steam. Forward
                # the callback through stdin, not an argv logged by Helper.
                body = base64.b64encode(b'EA sign-in received. Return to SkullKey.').decode()
                self.callback_sent = True
                await self.command('Fetch.fulfillRequest', {'requestId': identifier, 'responseCode': 200,
                                   'responseHeaders': [{'name': 'Content-Type', 'value': 'text/plain; charset=utf-8'},
                                                       {'name': 'Cache-Control', 'value': 'no-store'}],
                                   'body': body}, session)
                self.process.stdin.write((json.dumps({'type': 'callback', 'uri': locations[0]}) + '\n').encode())
                await self.process.stdin.drain()
            else:
                await self.command('Fetch.continueRequest', {'requestId': identifier}, session)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.fail('ea-browser-interception')

    async def read_worker(self):
        try:
            async def messages():
                while line := await self.process.stdout.readline():
                    # Shell initialization may print non-protocol lines. Never
                    # forward them to the frontend or logs.
                    try:
                        message = json.loads(line)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(message, dict):
                        continue
                    kind = message.get('type')
                    if kind == 'url' and login_url(message.get('url')) and self.initial_url is None:
                        self.initial_url = message['url']
                        if not self.first.done():
                            self.first.set_result({'ok': True, 'url': self.initial_url, 'platform': 'EA'})
                    elif kind == 'finishing':
                        self.state = {'status': 'finishing', 'platform': 'EA'}
                    elif kind == 'done':
                        if await self.process.wait() != 0:
                            raise RuntimeError('Worker did not confirm success')
                        self.state = {'status': 'done', 'platform': 'EA'}
                        if not self.first.done():
                            self.first.set_result({'ok': True, 'complete': True, 'platform': 'EA'})
                        return
                    elif kind == 'error':
                        self.fail('ea-login-failed')
                        return
                self.fail('ea-worker-exited')
            await asyncio.wait_for(messages(), 600)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.fail('ea-login-failed')
        finally:
            await self.close()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.first is not None and not self.first.done():
            self.first.set_result({'ok': False, 'error': 'ea-login-cancelled'})
        self.abort()
        if self.ws is not None:
            await self.ws.close()
        if self.reader is not None and self.reader is not asyncio.current_task():
            self.reader.cancel()
        for task in tuple(self.handlers):
            task.cancel()
        if self.monitor is not None and self.monitor is not asyncio.current_task():
            self.monitor.cancel()
        if self.http is not None:
            await self.http.close()
        if self.process is not None and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), 7)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
