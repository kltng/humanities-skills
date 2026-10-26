// Browser test for scripts/template.html, run under jsdom by test_template.py.
// Usage: node template_behavior.js <review.html>   (needs the jsdom package)

const { JSDOM } = require('jsdom');
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost/', pretendToBeVisual: true });
const w = dom.window, d = w.document;
w.HTMLElement.prototype.scrollIntoView = function(){};
let pass = 0, fail = 0;
function ok(c, m){ if (c) { pass++; console.log('PASS', m); } else { fail++; console.log('FAIL', m); } }
const ser = () => w.eval('serialize()').results;
const res = (item, q) => ser().find(r => r.item_id === item && r.question_id === q);
const ids = ser().map(r => [r.item_id, r.question_id]);
const qiOf = (item, q) => ids.findIndex(x => x[0] === item && x[1] === q);
const none = qi => d.querySelector('.none-input[data-qi="' + qi + '"]');
const cand = (qi, id) => d.querySelector('.cand-input[data-qi="' + qi + '"][data-id="' + id + '"]');
const key = k => d.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true }));
const [i1, i2] = [ser()[0].item_id, ser()[2].item_id];

// 1. match with preselected candidate: None should be selectable and clear candidates
let qi = qiOf(i1, 'm');
ok(res(i1,'m').selected.join() === 'c1', 'match: c1 preselected');
none(qi).click();
ok(res(i1,'m').none === true, 'match: None ticks while a candidate was preselected');
ok(res(i1,'m').selected.length === 0 && !cand(qi,'c1').checked, 'match: None clears candidates');
ok(none(qi).checked, 'match: None box shows ticked');
cand(qi,'c2').click();
ok(res(i1,'m').none === false && !none(qi).checked, 'match: ticking candidate clears None');
ok(res(i1,'m').selected.join() === 'c2', 'match: c2 selected');
// 2. single: None selectable
qi = qiOf(i1, 's');
cand(qi,'x1').click();
none(qi).click();
ok(res(i1,'s').none === true && res(i1,'s').selected.length === 0, 'single: None selectable, clears choice');
ok(none(qi).checked && !cand(qi,'x1').checked, 'single: UI shows None only');
cand(qi,'x2').click();
ok(res(i1,'s').none === false && res(i1,'s').selected.join() === 'x2', 'single: picking candidate clears None');
// 3. keyboard: focus second question of item 2
const qa = qiOf(i2,'a'), qb = qiOf(i2,'b');
w.eval('setFocus(' + qb + ')');
key('1');
ok(res(i2,'b').selected.join() === 'b1', 'kbd: key 1 acts on focused question b');
ok(res(i2,'a').selected.length === 0, 'kbd: question a untouched');
key('n');
ok(res(i2,'b').none === true && res(i2,'a').none === false, 'kbd: n toggles None on focused question b');
w.eval('setFocus(' + qiOf(i2,'r2') + ')');
key('3');
ok(res(i2,'r2').rating === 3 && res(i2,'r1').rating == null, 'kbd: rating key acts on focused rating question');
key('k'); key('k');
key('2');
ok(res(i2,'b').selected.join() === 'b2' && res(i2,'b').none === false, 'kbd: k moves focus back one question at a time');
ok(d.querySelectorAll('.kbd-focus').length >= 1, 'kbd: focus highlight present');
// 4. export / reload round trip
const exported = JSON.stringify(w.eval('serialize()'));
w.eval('render()');
const n = w.eval('applyResults(' + exported + ')');
ok(n === ser().length, 'reload: all answers applied (' + n + ')');
ok(none(qiOf(i1,'m')) && !none(qiOf(i1,'m')).checked && cand(qiOf(i1,'m'),'c2').checked, 'reload: UI state restored');
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
