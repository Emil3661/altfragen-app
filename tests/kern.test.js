// Prüft die Lernlogik gegen die gemeinsamen Testvektoren und eigene Fälle, ohne Bildschirm.
// Aufruf: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const K = require('../web/kern.js');

const V = path.join(__dirname, 'vektoren');
const lade = name => JSON.parse(fs.readFileSync(path.join(V, name), 'utf8'));
const daten = lade('fragen.json');
const ix = K.erschliessen(daten);
const md = fs.readFileSync(path.join(V, 'lernskript.md'), 'utf8');

// Erste Fundstelle ersetzen, wie in den Vektoren beschrieben
function ersetzt(text, paare) {
  for (const [alt, neu] of paare) {
    const i = text.indexOf(alt);
    assert.notStrictEqual(i, -1, `nicht gefunden: ${alt}`);
    text = text.slice(0, i) + neu + text.slice(i + alt.length);
  }
  return text;
}

// ---------- Vektoren: Lernskript lesen ----------
for (const fall of lade('lesen.json')) {
  test(`lesen: ${fall.name}`, () => {
    const text = fall.datei ? fs.readFileSync(path.join(V, fall.datei), 'utf8') : fall.text;
    const r = K.lernskriptLesen(text, ix);
    const schluessel = Object.fromEntries(Object.entries(r.zustaende).map(([id, z]) => [id, K.schluessel(z)]));
    assert.deepStrictEqual(schluessel, fall.zustaende);
    assert.deepStrictEqual(r.fehler, fall.fehler);
  });
}

// ---------- Vektoren: Wiederholung ----------
for (const fall of lade('wiederholung.json')) {
  test(`wiederholung: ${fall.name}`, () => {
    const q = ix.fragen.get(fall.frage).frage;
    const versuche = fall.versuche.map((v, i) => ({ id: 'v' + i, unsicher: false, falsch: false, geloescht: null, ...v }));
    const w = K.wiederholung(q, versuche, fall.heute, daten.klausur);
    assert.strictEqual(w.status, fall.status);
    assert.strictEqual(w.faellig, fall.faellig);
  });
}

// ---------- Vektoren: Fehlersammlung ----------
for (const fall of lade('fehler.json')) {
  test(`fehlerSammlung: ${fall.name}`, () => {
    const versuche = Object.fromEntries(Object.entries(fall.versuche).map(([id, vs]) =>
      [id, vs.map((v, i) => ({ id: `${id}:${i}`, unsicher: false, falsch: false, geloescht: null, ...v }))]));
    const r = K.fehlerSammlung(daten, { versuche });
    assert.deepStrictEqual(r.map(x => ({ frage: x.frage.id, falsch: x.falsch, unsicher: x.unsicher })), fall.erwartet);
  });
}

// ---------- Vektoren: Abgleich ----------
for (const fall of lade('abgleich.json')) {
  test(`abgleich: ${fall.name}`, () => {
    const text = ersetzt(md, fall.ersetze);
    const r = K.abgleichen(fall.fortschritt, text, fall.mdZeit, ix, fall.jetzt);
    const e = fall.erwartet;
    assert.strictEqual(r.abbruch, null);
    const versuche = {};
    for (const [id, liste] of Object.entries(r.fortschritt.versuche)) {
      versuche[id] = K.gueltige(liste).map(v => K.schluessel(v));
    }
    for (const id of Object.keys(e.versuche)) assert.deepStrictEqual(versuche[id] || [], e.versuche[id], `Versuche ${id}`);
    assert.deepStrictEqual([...r.geaendert].sort(), [...e.geaendert].sort());
    assert.deepStrictEqual(r.fortschritt.md.basis, e.basis);
    assert.deepStrictEqual(r.fortschritt.md.ueberschrieben, e.ueberschrieben);
    if (!e.geaendert.length) assert.strictEqual(r.mdNeu, null);
    const neu = r.mdNeu === null ? text : r.mdNeu;
    for (const [zeile, anzahl] of Object.entries(e.zeilen || {})) {
      assert.strictEqual(neu.split('\n').filter(z => z === zeile).length, anzahl, `Zeile ${zeile}`);
    }
  });
}

// ---------- Eigene Fälle ----------
test('Umschreiben ändert nur das Zeichen im Kästchen, auch bei Windows-Zeilenenden', () => {
  const text = md.replace(/\n/g, '\r\n');
  const f = { versuche: { '1.Q02': [{ id: 'a', zeit: '2026-11-08T21:00:00Z', wahl: ['Gurke'], geaendert: '2026-11-08T21:00:00Z', geloescht: null }] },
    md: { zeit: null, basis: {}, ueberschrieben: {} } };
  const r = K.abgleichen(f, text, '2026-11-08T17:25:00Z', ix, '2026-11-08T21:05:00Z');
  assert.deepStrictEqual(r.geaendert, ['1.Q02']);
  assert.strictEqual(r.mdNeu.length, text.length);
  const unterschiede = [...text].map((c, i) => [c, r.mdNeu[i], i]).filter(([a, b]) => a !== b);
  assert.strictEqual(unterschiede.length, 1);
  assert.strictEqual(unterschiede[0][1], 'x');
  assert.ok(r.mdNeu.includes('- [x] Gurke\r\n'));
});

test('Schutz: mehr als fünf geleerte Fragen halten den Abgleich an', () => {
  const zeilen = ['## 1 · Obst'];
  const big = { ...daten, themen: [{ ...daten.themen[0], fragen: [] }] };
  for (let n = 1; n <= 6; n++) {
    big.themen[0].fragen.push({ id: `1.Q${n}`, nr: n, typ: 'positiv', optionen: [{ t: 'Apfel', richtig: true }, { t: 'Banane', richtig: false }] });
    zeilen.push(`**Frage ${n}**`, '- [x] Apfel', '- [ ] Banane', '- [ ] *unsicher*');
  }
  const bix = K.erschliessen(big);
  const basis = Object.fromEntries(big.themen[0].fragen.map(q => [q.id, 'Apfel#u0f0']));
  const f = { versuche: {}, md: { zeit: '2026-11-08T20:00:00Z', basis, ueberschrieben: {} } };
  const r = K.abgleichen(f, zeilen.join('\n'), '2026-11-08T17:00:00Z', bix, '2026-11-08T21:00:00Z');
  assert.match(r.abbruch, /6 Fragen/);
  assert.strictEqual(r.mdNeu, null);
  assert.deepStrictEqual(r.fortschritt.md, f.md);
});

test('Zusammenführen: Grabstein und späteres geaendert gewinnen, Schritte je Feld', () => {
  const v = { id: 'x', zeit: '2026-11-08T10:00:00Z', wahl: ['Apfel'], geaendert: '2026-11-08T10:00:00Z', geloescht: null };
  const a = { fach: 'test', versuche: { '1.Q01': [v] }, schritte: { 1: { kern: { wert: 'ja', zeit: '2026-11-08T10:00:00Z' } } }, md: { zeit: '2026-11-08T10:00:00Z', basis: { a: 1 } } };
  const b = { fach: 'test', versuche: { '1.Q01': [{ ...v, geloescht: '2026-11-08T11:00:00Z', geaendert: '2026-11-08T11:00:00Z' }], '1.Q02': [{ ...v, id: 'y' }] },
    schritte: { 1: { kern: { wert: null, zeit: '2026-11-08T09:00:00Z' }, meditricks: { wert: 'keins', zeit: '2026-11-08T09:00:00Z' } } }, md: { zeit: '2026-11-08T09:00:00Z', basis: { b: 1 } } };
  for (const g of [K.zusammenfuehren(a, b), K.zusammenfuehren(b, a)]) {
    assert.strictEqual(g.versuche['1.Q01'].length, 1);
    assert.ok(g.versuche['1.Q01'][0].geloescht);
    assert.strictEqual(g.versuche['1.Q02'].length, 1);
    assert.strictEqual(g.schritte[1].kern.wert, 'ja');
    assert.strictEqual(g.schritte[1].meditricks.wert, 'keins');
    assert.deepStrictEqual(g.md.basis, { a: 1 });
  }
});

test('Abgleich ist wiederholbar: zweiter Lauf ändert nichts mehr', () => {
  const f = { versuche: { '1.Q02': [{ id: 'a', zeit: '2026-11-08T21:00:00Z', wahl: ['Gurke'], geaendert: '2026-11-08T21:00:00Z', geloescht: null }] } };
  const r1 = K.abgleichen(f, md, '2026-11-08T17:25:00Z', ix, '2026-11-08T21:05:00Z');
  const r2 = K.abgleichen(r1.fortschritt, r1.mdNeu, '2026-11-08T21:05:01Z', ix, '2026-11-08T21:06:00Z');
  assert.strictEqual(r2.mdNeu, null);
  assert.deepStrictEqual(r2.fortschritt.versuche, r1.fortschritt.versuche);
});

test('Zwei Geräte übernehmen denselben Docs-Haken nur einmal', () => {
  const leer = K.leererFortschritt('test');
  const a = K.abgleichen(leer, md, '2026-11-08T17:25:00Z', ix, '2026-11-08T21:00:00Z').fortschritt;
  const b = K.abgleichen(leer, md, '2026-11-08T17:25:00Z', ix, '2026-11-08T21:00:30Z').fortschritt;
  const g = K.zusammenfuehren(a, b);
  assert.strictEqual(g.versuche['1.Q01'].length, 1);
});

test('Plan: Blöcke mit Stufe A vor B, C am Ende als optional', () => {
  const t = (rang, block, stufe) => ({ rang, block, stufe, fragen: [] });
  const d = { plan: 'block-stufe', bloecke: [{ nr: 2 }, { nr: 1 }], themen: [t(1, 1, 'B'), t(2, 1, 'A'), t(3, 2, 'C'), t(4, 2, 'A'), t(5, 1, 'C')] };
  const p = K.planListe(d).map(x => `${x.thema.rang}${x.optional ? '?' : ''}`);
  assert.deepStrictEqual(p, ['4', '2', '1', '3?', '5?']);
});

test('Tempo und nächstes Thema', () => {
  const f = K.leererFortschritt('test');
  const tp = K.tempo(daten, f, '2027-02-01');
  assert.strictEqual(tp.ziel, '2027-02-05');
  assert.strictEqual(tp.tage, 5);
  assert.strictEqual(tp.offen, 4);
  assert.strictEqual(tp.proTag, 1);
  const n = K.naechstesThema(daten, f, '2026-11-09');
  assert.strictEqual(n.thema.rang, 1);
  assert.strictEqual(n.stand.naechste.id, '1.Q01');
});

test('Nächstes Thema, sobald alle Fragen einmal beantwortet sind, auch ohne Meditricks und Kern', () => {
  const f = K.leererFortschritt('test');
  K.versuchBuchen(f, '1.Q01', { wahl: ['Banane'] }, '2026-11-09T10:00:00Z', 'g');
  K.versuchBuchen(f, '1.Q02', { wahl: ['Gurke'] }, '2026-11-09T10:01:00Z', 'g');
  assert.strictEqual(K.naechstesThema(daten, f, '2026-11-09').thema.rang, 1);
  K.versuchBuchen(f, '1.Q03', { wahl: [], unsicher: true }, '2026-11-09T10:02:00Z', 'g');
  assert.strictEqual(K.naechstesThema(daten, f, '2026-11-09').thema.rang, 2);
});

test('Docs-Escapes zählen als dieselbe Option', () => {
  assert.strictEqual(K.normal('Birne 3\\. Klasse \\= gut  '), 'Birne 3. Klasse = gut');
  assert.strictEqual(K.normal('*unsicher*'), 'unsicher');
  assert.strictEqual(K.normal('**_falsch_**'), 'falsch');
});
