// Discs & Installers UI safety checks (source-level: these paths need Steam).
// Usage: node --test tests/test_disks_ui_safety.cjs
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const modal = fs.readFileSync(path.join(__dirname, '../src/Components/DiskAddModal.tsx'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, '../src/Components/GameDetailsItem.tsx'), 'utf8');

test('resumed dialog can be cancelled and cleans up', () => {
  const exeStep = modal.slice(modal.indexOf('case "exe-choose":'), modal.indexOf('case "error":'));
  assert.match(exeStep, /onClick=\{cancel\}/);
  assert.match(modal, /if \(\(!changeExe \|\| resumed\) && slug\.current\)/);
  assert.match(modal, /openDiskAdd\(serverAPI, onDone, resume, true\)/);
});

test('saves prompt: B cancels, it never deletes', () => {
  const ask = page.slice(page.indexOf('const askKeepSaves'), page.indexOf('const uninstall = async'));
  assert.match(ask, /onCancel=\{\(\) => finish\(null\)\}/);
  assert.doesNotMatch(ask, /onCancel=\{\(\) => resolve\(""\)\}/);
  assert.match(ask, /finish\("keep"\)/);
  assert.match(ask, /finish\(""\)/);
});

test('uninstall refuses while the game is running', () => {
  const ask = page.slice(page.indexOf('const askKeepSaves'), page.indexOf('const uninstall = async'));
  assert.match(ask, /RunningApps/);
});
