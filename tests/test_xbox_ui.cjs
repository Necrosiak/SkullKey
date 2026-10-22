// Xbox tab UI contracts. Usage: node --test tests/test_xbox_ui.cjs
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { test } = require("node:test");
const details = fs.readFileSync(path.join(__dirname, "../src/Components/GameDetailsItem.tsx"), "utf8");

test("Xbox installs ask which drive to use, like the other stores", () => {
  const m = details.match(/const drivePicker = \/\^\((.*?)\)Actions\$\//);
  assert.ok(m, "drive picker store list not found");
  assert.ok(m[1].split("|").includes("Xbox"));
});

test("entering a store grid lands on its first game, not under the button you came from", () => {
  const grid = fs.readFileSync(path.join(__dirname, "../src/Components/GridContent.tsx"), "utf8");
  assert.ok(grid.includes("navEntryPreferPosition={0}"));
});

test("settings have Installed games and Platforms pages", () => {
  const about = fs.readFileSync(path.join(__dirname, "../src/About.tsx"), "utf8");
  assert.ok(about.includes("<InstalledGamesPage") && about.includes("<PlatformsPage"));
  const pages = fs.readFileSync(path.join(__dirname, "../src/Components/SettingsPages.tsx"), "utf8");
  assert.ok(pages.includes("platforms_set") && pages.includes("installed: \"true\""));
});

test("settings strings exist in the 9 languages", () => {
  const i18n = fs.readFileSync(path.join(__dirname, "../src/i18n.ts"), "utf8");
  for (const key of ["tab_installed", "tab_platforms", "inst_move", "plat_desc"])
    assert.equal((i18n.match(new RegExp(key + ":", "g")) || []).length, 9, key);
});

test("every store page shows the anti-cheat warning", () => {
  const src = fs.readFileSync(path.join(__dirname, "../src/Components/GameDetailsItem.tsx"), "utf8");
  assert.ok(src.includes("\"compat_check\"") && src.includes("compatNote"));
  const i18n = fs.readFileSync(path.join(__dirname, "../src/i18n.ts"), "utf8");
  assert.equal((i18n.match(/compat_warn:/g) || []).length, 9);
});

test("Xbox grid has Owned / Game Pass / Free / Installed filters", () => {
  const grid = fs.readFileSync(path.join(__dirname, "../src/Components/GridContent.tsx"), "utf8");
  assert.ok(grid.includes("\"owned\", \"gamepass\", \"free\", \"installed\""));
  const i18n = fs.readFileSync(path.join(__dirname, "../src/i18n.ts"), "utf8");
  assert.equal((i18n.match(/xbox_filter_gamepass:/g) || []).length, 9);
});
