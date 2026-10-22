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
