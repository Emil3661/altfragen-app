// Prüft die Zerlegung der Markdown-Teilmenge ohne Bildschirm.
// Aufruf: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const M = require('../web/markdown.js');

const text = t => t.map(x => (x.t === 'text' ? x.s : `<${x.t}>${text(x.k)}</${x.t}>`)).join('');

test('fett, kursiv und Docs-Escapes', () => {
  assert.strictEqual(text(M.zeile('**Apfel** ist *rund*, 3\\. Klasse \\= gut')), '<fett>Apfel</fett> ist <kursiv>rund</kursiv>, 3. Klasse = gut');
  assert.strictEqual(text(M.zeile('5 * 3 = 15 und a_b_c')), '5 * 3 = 15 und a_b_c');
  assert.strictEqual(text(M.zeile('**offen')), '**offen');
});

test('verschachtelte Liste, Gruppenzeile beendet die Liste', () => {
  const b = M.bloecke('- **Klausurfokus:** Zuordnung\n**Vier Angriffsorte**\n- Zellwand\n- Proteinsynthese:  \n  - **30S**: Aminoglykoside\n  - 50S\n- Nukleinsäuren');
  assert.deepStrictEqual(b.map(x => x.t), ['liste', 'absatz', 'liste']);
  const l = b[2];
  assert.strictEqual(l.punkte.length, 3);
  assert.strictEqual(l.punkte[1].unter.punkte.length, 2);
  assert.strictEqual(text(l.punkte[1].unter.punkte[0].k), '<fett>30S</fett>: Aminoglykoside');
});

test('Tabelle ohne Kopf, Docs-Trennzeile', () => {
  const b = M.bloecke('|  |  |\n| :---- | :---- |\n| Cefazolin | Cephalosporin 1\\. Generation |\n| A | B |');
  assert.strictEqual(b.length, 1);
  assert.strictEqual(b[0].kopf, null);
  assert.strictEqual(b[0].zeilen.length, 2);
  assert.strictEqual(text(b[0].zeilen[0][1]), 'Cephalosporin 1. Generation');
});

test('Tabelle mit Kopf', () => {
  const b = M.bloecke('| # | Thema |\n|---|---|\n| 1 | Obst |');
  assert.strictEqual(text(b[0].kopf[1]), 'Thema');
  assert.strictEqual(b[0].zeilen.length, 1);
});

test('nummerierte Aussagen und Absätze mit Zeilenumbruch', () => {
  const b = M.bloecke('Erste Zeile\nzweite Zeile\n\n1. eins\n2. zwei');
  assert.strictEqual(b[0].zeilen.length, 2);
  assert.ok(b[1].geordnet);
  assert.strictEqual(b[1].punkte.length, 2);
});

test('HTML im Text bleibt Text', () => {
  const t = M.zeile('<img src=x onerror=alert(1)>');
  assert.deepStrictEqual(t, [{ t: 'text', s: '<img src=x onerror=alert(1)>' }]);
});
