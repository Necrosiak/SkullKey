// Discs & Installers dialog steps (pure state machine, no Steam needed).
// Usage: node --test tests/test_disks_flow_ui.cjs
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const ts = require('typescript');

const src = fs.readFileSync(path.join(__dirname, '../src/disksFlow.ts'), 'utf8');
const js = ts.transpileModule(src, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} };
new Function('module', 'exports', js)(mod, mod.exports);
const { initialState, nextStep, defaultCandidate } = mod.exports;

const run = (events) => events.reduce(nextStep, initialState());
const src_ = { type: 'source', kind: 'image', path: '/d/Game.iso', label: 'Game' };

test('image source goes through installer to done', () => {
  const steps = [];
  let s = initialState();
  for (const e of [src_, { type: 'title', title: 'Game' }, { type: 'drive', root: '' },
                   { type: 'prepared', stage: 'needs-installer' }, { type: 'installerStarted' },
                   { type: 'installerClosed' }, { type: 'candidates', list: [{ path: '/g.exe', score: 1, default_ok: true }] },
                   { type: 'exe', path: '/g.exe' }]) {
    s = nextStep(s, e);
    steps.push(s.step);
  }
  assert.deepEqual(steps, ['title', 'drive', 'preparing', 'installer-ready', 'installer-running',
                           'exe-loading', 'exe-choose', 'done']);
  assert.equal(s.exe, '/g.exe');
  assert.deepEqual(s.parts, ['/d/Game.iso']);
});

test('ready folder skips the installer', () => {
  const s = run([{ ...src_, kind: 'ready' }, { type: 'title', title: 'G' }, { type: 'drive', root: '/mnt/sd' },
                 { type: 'prepared', stage: 'ready' }]);
  assert.equal(s.step, 'exe-loading');
  assert.equal(s.root, '/mnt/sd');
});

test('empty candidates ask for a manual pick', () => {
  const s = run([src_, { type: 'title', title: 'G' }, { type: 'drive', root: '' },
                 { type: 'prepared', stage: 'ready' }, { type: 'candidates', list: [] }]);
  assert.equal(s.step, 'exe-manual');
});

test('cancel from any step is final', () => {
  for (let n = 0; n <= 4; n++) {
    const events = [src_, { type: 'title', title: 'G' }, { type: 'drive', root: '' },
                    { type: 'prepared', stage: 'needs-installer' }].slice(0, n);
    const s = run([...events, { type: 'cancel' }, { type: 'title', title: 'x' }]);
    assert.equal(s.step, 'cancelled');
  }
});

test('blank title is refused and events out of order are ignored', () => {
  let s = run([src_, { type: 'title', title: '   ' }]);
  assert.equal(s.step, 'title');
  s = nextStep(s, { type: 'installerClosed' });
  assert.equal(s.step, 'title');
});

test('default candidate skips config tools', () => {
  assert.equal(defaultCandidate([{ path: '/config.exe', score: 9, default_ok: false },
                                 { path: '/g.exe', score: 1, default_ok: true }]).path, '/g.exe');
  assert.equal(defaultCandidate([{ path: '/config.exe', score: 9, default_ok: false }]), undefined);
});
