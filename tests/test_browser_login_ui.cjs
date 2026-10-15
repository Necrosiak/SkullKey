// Run the actual TS login function with fake RPC/navigation/timers, no account.
// Usage: node --test tests/test_browser_login_ui.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const ts = require('typescript');
const text = fs.readFileSync(path.join(__dirname, '../src/Components/LoginContent.tsx'), 'utf8');
const start = text.indexOf('const startBrowserLogin =');
const end = text.indexOf('export const LoginContent');
assert.ok(start >= 0 && end > start);
const source = ts.transpileModule(
  'let browserPoll = null; let browserLoginError = "";\n' + text.slice(start, end) +
  '\nglobalThis.start = startBrowserLogin; globalThis.error = () => browserLoginError;',
  { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None } }
).outputText;

async function run(response, status = { success: true, result: { status: 'done' } }) {
  const calls = [];
  let poll;
  const context = vm.createContext({
    Navigation: { Navigate: route => calls.push(['route', route]),
                  NavigateToExternalWeb: url => calls.push(['web', url]) },
    setInterval: fn => { poll = fn; calls.push(['timer']); return 1; },
    clearInterval: () => calls.push(['clear']), Date,
  });
  vm.runInContext(source, context);
  const result = await context.start({ callPluginMethod: async method => {
    calls.push(['rpc', method]);
    return method === 'browser_login_start' ? response : status;
  } }, 'EALoginActions', '/fixture');
  return { result, calls, error: context.error, poll: () => poll() };
}

for (const [name, response] of [
  ['RPC failure', { success: false, result: 'fixture-error' }],
  ['backend failure', { success: true, result: { ok: false, error: 'fixture-error' } }],
  ['missing result', { success: true }],
  ['missing interactive URL', { success: true, result: { ok: true } }],
  ['failed response with complete flag', { success: true, result: { ok: false, complete: true } }],
]) {
  test(name + ' does not navigate', async () => {
    const actual = await run(response);
    assert.equal(actual.result, false);
    assert.ok(actual.error());
    assert.equal(actual.calls.filter(x => ['route', 'web', 'timer'].includes(x[0])).length, 0);
    if (name === 'backend failure') assert.equal(actual.error(), 'fixture-error');
  });
}

test('already connected without URL returns to store without browser or polling', async () => {
  const actual = await run({ success: true, result: { ok: true, complete: true } });
  assert.equal(actual.result, true);
  assert.equal(actual.error(), '');
  assert.deepEqual(actual.calls.filter(x => x[0] !== 'rpc'), [['route', '/fixture']]);
});

test('EA CDP startup failure keeps its specific category instead of generic RPC error', async () => {
  const actual = await run({ success: true, result: { ok: false, error: 'ea-browser-start' } });
  assert.equal(actual.result, false);
  assert.equal(actual.error(), 'ea-browser-start');
  assert.ok(!actual.calls.some(x => x[0] === 'web'));
});

test('interactive URL opens browser and starts polling', async () => {
  const actual = await run({ success: true, result: { ok: true, url: 'https://fixture.invalid/' } });
  assert.equal(actual.result, true);
  assert.equal(actual.error(), '');
  assert.deepEqual(actual.calls.filter(x => x[0] !== 'rpc'), [['web', 'https://fixture.invalid/'], ['timer']]);
  await actual.poll();
  assert.ok(actual.calls.some(x => x[0] === 'clear'));
  assert.ok(actual.calls.some(x => x[0] === 'route' && x[1] === '/fixture'));
  assert.ok(!actual.calls.some(x => x[1] === 'browser_login_cancel'));
});

test('interactive error cancels and returns to store', async () => {
  const actual = await run({ success: true, result: { ok: true, url: 'https://fixture.invalid/' } },
    { success: true, result: { status: 'error', message: 'fixture-worker-error' } });
  await actual.poll();
  assert.equal(actual.error(), 'fixture-worker-error');
  assert.ok(actual.calls.some(x => x[1] === 'browser_login_cancel'));
  assert.ok(actual.calls.some(x => x[0] === 'route'));
});

// Exercise the real caller as well: the same login button chooses the path
// for every store based on GTK/WebKit availability, not on the store name.
const loginStart = text.indexOf('const login = async () =>');
const loginEnd = text.indexOf('const logout = async () =>', loginStart);
assert.ok(loginStart >= 0 && loginEnd > loginStart);
const callerSource = ts.transpileModule(text.slice(loginStart, loginEnd) +
  '\nglobalThis.login = login;',
  { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None } }
).outputText;

async function runCaller(store, needsBrowser, response) {
  const calls = [];
  const context = vm.createContext({
    serverAPI: { callPluginMethod: async (method, args) => {
      calls.push(['rpc', method, args]);
      return method === 'browser_login_needed' ? { success: true, result: needsBrowser } : response;
    } },
    actionSetName: store + 'LoginActions', originRoute: '/fixture',
    Navigation: { Navigate: route => calls.push(['route', route]),
                  NavigateToExternalWeb: url => calls.push(['web', url]) },
    setInterval: () => 1, clearInterval: () => {}, Date,
    setContent: content => calls.push(['content', content]),
    setLoggedIn: state => calls.push(['logged', state]),
    executeAction: async (_api, actionSet, action) => {
      calls.push(['action', actionSet, action]);
      return { Content: { Name: 'Fixture', Exe: '/fixture' } };
    },
    getSteamClientId: async () => 123, gameIDFromAppID: () => 'fixture',
    onLoginExit: () => {}, t: key => key,
    logger: { debug: () => {}, error: error => calls.push(['error', error]) },
  });
  vm.runInContext(source + '\n' + callerSource, context);
  await context.login();
  assert.ok(!calls.some(x => x[0] === 'error'));
  return calls;
}

for (const store of ['EA', 'GOG', 'Epic', 'Amazon']) {
  test(store + ': GTK/WebKit path bypasses browser_login_start entirely', async () => {
    const calls = await runCaller(store, false);
    assert.deepEqual(calls.filter(x => x[0] === 'action').map(x => x.slice(1)),
      [[store + 'LoginActions', 'LoginLaunchOptions'], [store + 'LoginActions', 'Login']]);
    assert.ok(!calls.some(x => x[1] === 'browser_login_start' || x[0] === 'web'));
  });

  test(store + ': fallback requests the same public RPC and opens returned URL', async () => {
    const calls = await runCaller(store, true,
      { success: true, result: { ok: true, url: 'https://fixture.invalid/' } });
    const rpc = calls.find(x => x[1] === 'browser_login_start');
    assert.equal(rpc[2].actionSet, store + 'LoginActions');
    assert.ok(calls.some(x => x[0] === 'web'));
    assert.ok(!calls.some(x => x[0] === 'action'));
  });

  test(store + ': fallback RPC failure produces generic error before browser', async () => {
    const calls = await runCaller(store, true, { success: false, result: 'fixture-TypeError' });
    const content = calls.find(x => x[0] === 'content')[1];
    assert.equal(content.Type, 'Error');
    assert.equal(content.Content.Data, 'browser login failed');
    assert.equal(content.Content.ActionSet, store + 'LoginActions');
    assert.ok(!calls.some(x => x[0] === 'web' || x[0] === 'action'));
  });
}
