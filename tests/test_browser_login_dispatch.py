"""Actual public RPC methods under Decky's legacy class-as-self contract.

No real worker, subprocess, browser or account; only external services are mocked.
"""
import ast
import asyncio
import json
from pathlib import Path
import time
import types
import unittest
from unittest.mock import AsyncMock, Mock


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, result=None):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8'))
        plugin = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Plugin')
        methods = [n for n in plugin.body if isinstance(n, ast.AsyncFunctionDef) and n.name in (
            'browser_login_start', '_browser_login_start', 'browser_login_status', 'browser_login_cancel')]
        state = types.SimpleNamespace(start_lock=asyncio.Lock(), ea=None, task=None,
                                      state={'status': 'idle'}, _watch=AsyncMock())
        worker = types.SimpleNamespace(start=AsyncMock(return_value=result or {'ok': True, 'url': 'https://fixture.invalid/'}),
                                       close=AsyncMock(), state={'status': 'waiting'})
        helper = types.SimpleNamespace(
            get_action=lambda name, _: {'Command': './scripts/skullkey.sh ' + name.removesuffix('LoginActions') + ' login'},
            get_environment=lambda _: {}, working_directory='/fixture',
            call_script=AsyncMock(return_value=json.dumps({'Content': {'Url': 'https://fixture.invalid/'}})))
        ns = dict(BrowserLogin=state, Helper=helper, BROWSER_LOGIN={'Epic': {}, 'GOG': {}, 'Amazon': {}},
                  _ea_browser=types.SimpleNamespace(EASteamBrowser=lambda: worker),
                  decky_plugin=types.SimpleNamespace(logger=Mock()), json=json, asyncio=asyncio, time=time)
        isolated = ast.Module(body=[ast.ClassDef(name='Plugin', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(isolated), '<rpc-contract>', 'exec'), ns)
        return ns['Plugin'], state, worker, helper

    async def start(self, plugin, store='EA'):
        return await plugin.browser_login_start(plugin, actionSet=store + 'LoginActions')

    async def test_legacy_ea_reaches_worker(self):
        plugin, state, worker, helper = self.fixture()
        self.assertTrue((await self.start(plugin))['ok'])
        self.assertIs(state.ea, worker)
        worker.start.assert_awaited_once()
        self.assertEqual(worker.start.call_args.args[0][-2:], ['EA', 'login-browser'])
        helper.call_script.assert_not_awaited()

    async def test_regular_instance_still_works(self):
        plugin, *_ = self.fixture()
        self.assertTrue((await plugin().browser_login_start('EALoginActions'))['ok'])

    async def test_existing_store_protocols_unchanged(self):
        for store in ('Epic', 'GOG', 'Amazon'):
            with self.subTest(store=store):
                plugin, state, worker, helper = self.fixture()
                self.assertTrue((await self.start(plugin, store))['ok'])
                helper.call_script.assert_awaited_once_with('./scripts/skullkey.sh', store, 'login-url')
                worker.start.assert_not_awaited()
                await state.task

    async def test_unknown_store_is_controlled_failure(self):
        plugin, _, worker, _ = self.fixture()
        self.assertFalse((await self.start(plugin, 'Unknown'))['ok'])
        worker.start.assert_not_awaited()

    async def test_worker_results_preserved(self):
        for result in ({'ok': True, 'complete': True}, {'ok': False, 'error': 'fixture-error'}):
            with self.subTest(result=result):
                plugin, *_ = self.fixture(result)
                self.assertEqual(await self.start(plugin), result)

    async def test_exception_releases_lock_and_allows_retry(self):
        plugin, state, worker, _ = self.fixture()
        worker.start.side_effect = [RuntimeError('fixture-error'), {'ok': True, 'complete': True}]
        self.assertEqual(await self.start(plugin), {'ok': False, 'error': 'fixture-error'})
        self.assertFalse(state.start_lock.locked())
        self.assertTrue((await self.start(plugin))['ok'])

    async def test_concurrent_starts_are_serialized(self):
        plugin, _, worker, _ = self.fixture()
        active = maximum = 0

        async def start(*args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)
            active -= 1
            return {'ok': True, 'complete': True}

        worker.start.side_effect = start
        self.assertTrue(all(r['ok'] for r in await asyncio.gather(*(self.start(plugin) for _ in range(3)))))
        self.assertEqual(maximum, 1)
        self.assertEqual(worker.close.await_count, 2)

    async def test_status_and_cancel_use_legacy_contract(self):
        plugin, state, worker, _ = self.fixture()
        await self.start(plugin)
        self.assertEqual((await plugin.browser_login_status(plugin))['status'], 'waiting')
        self.assertTrue((await plugin.browser_login_cancel(plugin))['ok'])
        worker.close.assert_awaited_once()
        self.assertIsNone(state.ea)
        self.assertEqual((await plugin.browser_login_status(plugin))['status'], 'idle')


if __name__ == '__main__':
    unittest.main()
