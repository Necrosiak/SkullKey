const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = process.argv[2] || path.join(__dirname, '../src/Utils/topBarPlacement.ts');
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
}).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { topBarHolder } = context.exports;

class Element {
    constructor(tag, x, width, height = 40) {
        this.tag = tag; this.rect = { left: x, right: x + width, width, height, top: 0 };
        this.children = []; this.parentElement = null; this.attrs = {}; this.style = {};
        this.display = 'flex'; this.direction = 'row';
    }
    append(child) { child.parentElement = this; this.children.push(child); return child; }
    get isConnected() { return this.root || !!this.parentElement?.isConnected; }
    getBoundingClientRect() { return this.rect; }
    hasAttribute(name) { return name in this.attrs; }
    setAttribute(name, value) { this.attrs[name] = value; }
    remove() {
        if (this.parentElement) this.parentElement.children.splice(this.parentElement.children.indexOf(this), 1);
        this.parentElement = null;
    }
    insertBefore(child, before) {
        assert.equal(before.parentElement, this);
        child.remove(); child.parentElement = this;
        this.children.splice(this.children.indexOf(before), 0, child);
    }
}
function fixture() {
    const row = new Element('row', 0, 1500); row.root = true;
    const button = row.append(new Element('button', 900, 42));
    const battery = button.append(new Element('battery', 910, 22));
    // Three SVG layers in ONE controller control, reproducing the real bug.
    for (let i = 0; i < 3; i++) battery.append(new Element('svg', 910, 20, 20));
    for (let x of [950, 1000, 1050]) row.append(new Element('button', x, 42)).append(new Element('svg', x + 10, 20, 20));
    const all = () => { const out = []; function walk(e) { out.push(e); e.children.forEach(walk); } walk(row); return out; };
    const doc = {
        defaultView: { innerWidth: 1500, getComputedStyle: e => ({ display: e.display, flexDirection: e.direction }) },
        querySelector: () => all().find(e => e.hasAttribute('data-sk-topbar')) || null,
        querySelectorAll: () => all().filter(e => e.tag === 'svg'),
        createElement: () => new Element('holder', 0, 40)
    };
    return { row, button, battery, doc };
}
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
test('multi-SVG controller stays intact; indicator is a separate row slot', () => {
    const { row, battery, doc } = fixture(); const h = topBarHolder(doc);
    assert.equal(h.parentElement, row); assert.equal(row.children[0], h);
    assert.equal(battery.children.length, 3); assert.match(h.style.cssText, /flex:0 0 40px/);
});
test('repeated polling reuses a valid holder without duplicates', () => {
    const { row, doc } = fixture(); const first = topBarHolder(doc);
    assert.equal(topBarHolder(doc), first); assert.equal(row.children.filter(e=>e.hasAttribute('data-sk-topbar')).length,1);
});
test('holder from old build nested inside battery is repaired', () => {
    const { battery, row, doc } = fixture(); const old = battery.append(new Element('holder',910,40));
    old.setAttribute('data-sk-topbar',''); const h = topBarHolder(doc);
    assert.equal(old.parentElement,null); assert.equal(h.parentElement,row); assert.equal(battery.children.length,3);
});
test('unknown layout fails closed rather than nesting inside a control', () => {
    const { doc, row } = fixture(); row.display = 'block'; assert.equal(topBarHolder(doc),null);
});
test('overlapping layers are not treated as a row', () => {
    const { doc, row } = fixture(); row.children.forEach(e => { e.rect.left=910; e.rect.right=952; });
    assert.equal(topBarHolder(doc),null);
});
test('Steam redraw creates a fresh holder only in a valid row', () => {
    const { doc, row } = fixture(); const first = topBarHolder(doc); first.remove();
    const second = topBarHolder(doc); assert.notEqual(second,first); assert.equal(second.parentElement,row);
});
test('missing window has no side effects', () => {
    const { doc, row } = fixture(); doc.defaultView=null; assert.equal(topBarHolder(doc),null); assert.equal(row.children.length,4);
});
test('a vertical group is not a horizontal top bar', () => {
    const { doc, row } = fixture(); row.direction='column'; assert.equal(topBarHolder(doc),null);
});
console.log(`${passed} placement tests passed`);
