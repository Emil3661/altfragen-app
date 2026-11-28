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

// ---------- Vektoren: Ergebnis je Frage ----------
// Beantwortet, Ergebnis der letzten Antwort und Zahl der falschen, aus allen Versuchen einer Frage
for (const fall of lade('ergebnis.json')) {
  test(`ergebnis: ${fall.name}`, () => {
    const q = ix.fragen.get(fall.frage).frage;
    const versuche = fall.versuche.map((v, i) => ({ id: 'v' + i, unsicher: false, falsch: false, geloescht: null, ...v }));
    const vs = K.ergebnisse(q, versuche);
    assert.strictEqual(K.beantwortet(q, versuche), fall.beantwortet);
    assert.strictEqual(vs.length ? vs[vs.length - 1].e : null, fall.letztes);
    assert.strictEqual(K.falschZahl(q, versuche), fall.falsch);
  });
}

// ---------- Vektoren: Sammlungen Falsch und Markiert ----------
// Der Fortschritt läuft vorher durch vervollstaendigen, wie in der App, damit das alte Merkmal unsicher zum Stern wird
for (const fall of lade('sammlung.json')) {
  test(`sammlung: ${fall.name}`, () => {
    const versuche = Object.fromEntries(Object.entries(fall.versuche).map(([id, vs]) =>
      [id, vs.map((v, i) => ({ id: `${id}:${i}`, unsicher: false, falsch: false, geloescht: null, ...v }))]));
    const f = K.vervollstaendigen({ versuche, sterne: fall.sterne || {} }, 'test');
    assert.deepStrictEqual(K.falschSammlung(daten, f).map(x => ({ frage: x.frage.id, falsch: x.falsch })), fall.erwartet.falsch);
    assert.deepStrictEqual(K.markiertSammlung(daten, f).map(x => x.frage.id), fall.erwartet.markiert);
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
    // Sterne: alle Fragen, deren Stern nach dem Abgleich an ist
    const an = [...ix.fragen.keys()].filter(id => K.sternAn(r.fortschritt, id)).sort();
    assert.deepStrictEqual(an, e.sterne, 'Sterne');
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
  const n = K.naechstesThema(daten, f);
  assert.strictEqual(n.thema.rang, 1);
  assert.strictEqual(n.stand.naechste.id, '1.Q01');
});

test('Tempo mit eigenem Zieldatum des Fachs', () => {
  const f = K.leererFortschritt('test');
  // Ziel einen Tag vor der Klausur statt sieben
  const tp = K.tempo({ ...daten, durchgang: '2027-02-11' }, f, '2027-02-08');
  assert.strictEqual(tp.ziel, '2027-02-11');
  assert.strictEqual(tp.tage, 4);
  assert.strictEqual(tp.proTag, 1);
  assert.strictEqual(tp.bisKlausur, 4);
});

test('Nächstes Thema, sobald alle Fragen einmal beantwortet sind, auch ohne Meditricks und Kern', () => {
  const f = K.leererFortschritt('test');
  K.versuchBuchen(f, '1.Q01', { wahl: ['Banane'] }, '2026-11-09T10:00:00Z', 'g');
  K.versuchBuchen(f, '1.Q02', { wahl: ['Gurke'] }, '2026-11-09T10:01:00Z', 'g');
  assert.strictEqual(K.naechstesThema(daten, f).thema.rang, 1);
  K.versuchBuchen(f, '1.Q03', { wahl: [], unsicher: true }, '2026-11-09T10:02:00Z', 'g');
  assert.strictEqual(K.naechstesThema(daten, f).thema.rang, 2);
});

test('Docs-Escapes zählen als dieselbe Option', () => {
  assert.strictEqual(K.normal('Birne 3\\. Klasse \\= gut  '), 'Birne 3. Klasse = gut');
  assert.strictEqual(K.normal('*unsicher*'), 'unsicher');
  assert.strictEqual(K.normal('**_falsch_**'), 'falsch');
});

// ---------- Stern ----------
const appVersuch = (id, zeit, wahl, merkmale = {}) => ({ id, zeit, wahl, unsicher: false, falsch: false, quelle: 'app', geaendert: zeit, geloescht: null, ...merkmale });
const stern = (wert, zeit) => ({ wert, zeit });

test('Stern: altes Merkmal unsicher wird übernommen, zurückgenommene und umgeschaltete nicht', () => {
  const f = K.vervollstaendigen({ versuche: {
    '1.Q01': [appVersuch('a', '2026-11-08T10:00:00Z', ['Apfel'], { unsicher: true }), appVersuch('b', '2026-11-09T10:00:00Z', ['Apfel'], { unsicher: true }), appVersuch('c', '2026-11-10T10:00:00Z', ['Apfel'])],
    '1.Q02': [appVersuch('d', '2026-11-08T10:00:00Z', ['Gurke'], { unsicher: true, geloescht: '2026-11-08T11:00:00Z' })],
    '1.Q03': [appVersuch('e', '2026-11-08T10:00:00Z', [], { unsicher: true })],
    '2.Q01': [appVersuch('g', '2026-11-08T10:00:00Z', ['Erbse'], { unsicher: true })],
  }, sterne: { '1.Q03': stern(false, '2026-11-09T10:00:00Z') } }, 'test');
  assert.deepStrictEqual(f.sterne, { '1.Q01': { ...stern(true, '2026-11-09T10:00:00Z'), alt: true }, '1.Q03': stern(false, '2026-11-09T10:00:00Z'),
    '2.Q01': { ...stern(true, '2026-11-08T10:00:00Z'), alt: true } });
  assert.deepStrictEqual(K.vervollstaendigen(JSON.parse(JSON.stringify(f)), 'test'), f);
});

test('Stern: unbrauchbare Einträge werden verworfen', () => {
  const f = K.vervollstaendigen({ sterne: { a: stern('ja', '2026-11-08T10:00:00Z'), b: stern(true, 'gestern'), c: null, d: stern(false, '2026-11-08T10:00:00Z') } }, 'test');
  assert.deepStrictEqual(f.sterne, { d: stern(false, '2026-11-08T10:00:00Z') });
  assert.deepStrictEqual(K.vervollstaendigen({ sterne: 'kaputt' }, 'test').sterne, {});
});

test('Stern: Zusammenführen nach Zeit, bei gleicher Zeit gewinnt der gesetzte, in beiden Richtungen gleich', () => {
  const a = { sterne: { '1.Q01': stern(true, '2026-11-08T10:00:00Z'), '1.Q02': stern(false, '2026-11-08T12:00:00Z'), '1.Q03': stern(false, '2026-11-08T10:00:00Z') } };
  const b = { sterne: { '1.Q01': stern(false, '2026-11-08T11:00:00Z'), '1.Q02': stern(true, '2026-11-08T11:00:00Z'), '1.Q03': stern(true, '2026-11-08T10:00:00Z'), '2.Q01': stern(true, '2026-11-08T09:00:00Z') } };
  for (const g of [K.zusammenfuehren(a, b), K.zusammenfuehren(b, a)]) {
    assert.deepStrictEqual(Object.fromEntries(Object.entries(g.sterne).map(([id, s]) => [id, s.wert])), { '1.Q01': false, '1.Q02': false, '1.Q03': true, '2.Q01': true });
  }
});

test('Stern: ein Stand ohne Sterne (ältere Fassung der App) löscht keinen', () => {
  const v = appVersuch('a', '2026-11-08T10:00:00Z', ['Apfel']);
  const mit = { versuche: { '1.Q01': [v] }, sterne: { '1.Q01': stern(true, '2026-11-08T10:01:00Z'), '1.Q02': stern(false, '2026-11-08T10:02:00Z') } };
  const ohne = { versuche: { '1.Q01': [v] } };
  for (const g of [K.zusammenfuehren(mit, ohne), K.zusammenfuehren(ohne, mit)]) assert.deepStrictEqual(g.sterne, mit.sterne);
});

test('Stern: ausgeschaltet bleibt aus, auch gegen einen Stand mit dem alten Merkmal', () => {
  const alt = { versuche: { '1.Q01': [appVersuch('a', '2026-11-08T10:00:00Z', ['Apfel'], { unsicher: true })] } };
  const a = K.vervollstaendigen(JSON.parse(JSON.stringify(alt)), 'test');
  K.sternSetzen(a, '1.Q01', false, '2026-11-16T18:00:00Z');
  for (const g of [K.zusammenfuehren(a, alt), K.zusammenfuehren(alt, a)]) assert.strictEqual(K.sternAn(g, '1.Q01'), false);
});

test('Stern: macht keine Frage beantwortet, zählt falsche Versuche ohne zurückgenommene', () => {
  const f = K.leererFortschritt('test');
  K.sternSetzen(f, '1.Q01', true, '2026-11-08T10:00:00Z');
  assert.strictEqual(K.tempo(daten, f, '2026-11-09').offen, 4);
  assert.strictEqual(K.themaStand(daten.themen[0], f).beantwortet, 0);
  const vs = [appVersuch('a', '2026-11-08T10:00:00Z', ['Banane']), appVersuch('b', '2026-11-09T10:00:00Z', ['Apfel']),
    appVersuch('c', '2026-11-10T10:00:00Z', ['Banane']), appVersuch('d', '2026-11-11T10:00:00Z', ['Banane'], { geloescht: '2026-11-11T10:01:00Z' })];
  assert.strictEqual(K.falschZahl(ix.fragen.get('1.Q01').frage, vs), 2);
});

test('Stern: Versuche aus Docs tragen kein unsicher, zwei Geräte kommen zum selben Stern', () => {
  const leer = K.leererFortschritt('test');
  const a = K.abgleichen(leer, md, '2026-11-08T17:25:00.000Z', ix, '2026-11-08T21:00:00.000Z').fortschritt;
  const b = K.abgleichen(leer, md, '2026-11-08T18:40:00.000Z', ix, '2026-11-08T22:00:00.000Z').fortschritt;
  const g = K.zusammenfuehren(a, b);
  assert.ok(Object.values(g.versuche).flat().every(v => !v.unsicher));
  assert.deepStrictEqual(Object.fromEntries(Object.entries(g.versuche).map(([id, vs]) => [id, vs.map(v => v.id)])),
    { '1.Q01': ['docs:1.Q01:Apfel#u0f0:0'], '1.Q03': ['docs:1.Q03:#u0f1:0'], '2.Q01': ['docs:2.Q01:Erbse|Gurke#u0f0:0'] });
  assert.deepStrictEqual(Object.keys(g.sterne).filter(id => K.sternAn(g, id)), ['1.Q01']);
});

test('Stern: alte Basis mit unsicher am letzten Versuch und unveränderte .md ergeben nichts zu tun', () => {
  const f = { versuche: { '1.Q01': [appVersuch('a', '2026-11-08T17:00:00Z', ['Apfel'], { unsicher: true })], '1.Q03': [appVersuch('b', '2026-11-08T17:00:00Z', [], { falsch: true })],
    '2.Q01': [appVersuch('c', '2026-11-08T17:00:00Z', ['Erbse', 'Gurke'])] },
  md: { zeit: '2026-11-08T17:30:00Z', basis: { '1.Q01': 'Apfel#u1f0', '1.Q03': '#u0f1', '2.Q01': 'Erbse|Gurke#u0f0' }, ueberschrieben: {} } };
  const r = K.abgleichen(f, md, '2026-11-08T17:25:00.000Z', ix, '2026-11-08T21:00:00.000Z');
  assert.deepStrictEqual(r.geaendert, []);
  assert.strictEqual(r.mdNeu, null);
  assert.ok(K.sternAn(r.fortschritt, '1.Q01'));
});

test('Stern: ein veralteter Stand hält einen übernommenen Stern nach dem Zusammenführen nicht fest', () => {
  const x = appVersuch('x', '2026-11-01T10:00:00Z', ['Apfel']);
  const y = appVersuch('y', '2026-11-08T10:00:00Z', ['Apfel'], { unsicher: true });
  for (const drive of [{ ...y, unsicher: false, geaendert: '2026-11-08T12:00:00Z' }, { ...y, geloescht: '2026-11-08T12:00:00Z', geaendert: '2026-11-08T12:00:00Z' }]) {
    const veraltet = K.vervollstaendigen({ versuche: { '1.Q01': [x, y] } }, 'test');
    for (const [a, b] of [[veraltet, { versuche: { '1.Q01': [x, drive] } }], [{ versuche: { '1.Q01': [x, drive] } }, veraltet]]) {
      const g = K.zusammenfuehren(a, b);
      assert.strictEqual(K.sternAn(g, '1.Q01'), false);
    }
  }
});

test('Ohne Wiederholung: altes Merkmal unsicher ändert kein Ergebnis, Stern aus nimmt die Frage aus Markiert', () => {
  let f = K.vervollstaendigen({ versuche: { '1.Q01': [appVersuch('a', '2026-11-08T10:00:00Z', ['Apfel'], { unsicher: true })] } }, 'test');
  const st = K.themaStand(daten.themen[0], f);
  assert.deepStrictEqual([st.beantwortet, st.richtig, st.falsch], [1, 1, 0]);
  assert.deepStrictEqual(K.markiertSammlung(daten, f).map(x => x.frage.id), ['1.Q01']);
  K.sternSetzen(f, '1.Q01', false, '2026-11-09T08:00:00Z');
  f = K.vervollstaendigen(f, 'test');
  assert.deepStrictEqual(K.markiertSammlung(daten, f), []);
  assert.deepStrictEqual(Object.keys(f.versuche['1.Q01'][0]).sort(), ['falsch', 'geaendert', 'geloescht', 'id', 'quelle', 'unsicher', 'wahl', 'zeit']);
});

test('Schutz: hält auch an, wenn nur noch Sterne da sind und die Antworten aus der .md flögen', () => {
  const zeilen = ['## 1 · Obst'];
  const big = { ...daten, themen: [{ ...daten.themen[0], fragen: [] }] };
  for (let n = 1; n <= 6; n++) {
    big.themen[0].fragen.push({ id: `1.Q${n}`, nr: n, typ: 'positiv', optionen: [{ t: 'Apfel', richtig: true }, { t: 'Banane', richtig: false }] });
    zeilen.push(`**Frage ${n}**`, '- [x] Apfel', '- [ ] Banane', '- [x] *unsicher*');
  }
  const bix = K.erschliessen(big);
  const ids = big.themen[0].fragen.map(q => q.id);
  const f = { versuche: {}, sterne: Object.fromEntries(ids.map(id => [id, stern(true, '2026-11-08T19:00:00Z')])),
    md: { zeit: '2026-11-08T20:00:00Z', basis: Object.fromEntries(ids.map(id => [id, 'Apfel#u1f0'])), ueberschrieben: {} } };
  const r = K.abgleichen(f, zeilen.join('\n'), '2026-11-08T17:00:00Z', bix, '2026-11-08T21:00:00Z');
  assert.match(r.abbruch, /6 Fragen/);
  assert.strictEqual(r.mdNeu, null);
});

test('Thema: zählt die letzte Antwort nach Zeit, leere Wahl macht nichts beantwortet', () => {
  const f = K.leererFortschritt('test');
  f.versuche['1.Q01'] = [appVersuch('b', '2026-11-10T10:00:00Z', ['Apfel']), appVersuch('a', '2026-11-08T10:00:00Z', ['Banane'])];
  f.versuche['1.Q02'] = [appVersuch('c', '2026-11-08T10:00:00Z', [])];
  const st = K.themaStand(daten.themen[0], f);
  assert.deepStrictEqual([st.gesamt, st.beantwortet, st.richtig, st.falsch, st.naechste.id, st.fertig], [3, 1, 1, 0, '1.Q02', false]);
});

test('Ranking: Zahlen aus meta, kumuliert ersatzweise summiert, Haken als Schritt', () => {
  const d = { themen: [
    { rang: 2, titel: 'Zwei', stufe: 'B', meta: 'erwartet 1,7 von 40 Fragen · Trend fallend' },
    { rang: 1, titel: 'Eins', stufe: 'A', meta: 'erwartet 3,1 von 40 Fragen · 32 Altfragen · Trend steigend · kumuliert 8 %' },
    { rang: 3, titel: 'Drei', stufe: null, meta: '8 Fragen, 15 Nennungen' },
  ] };
  const f = K.leererFortschritt('test');
  K.schrittSetzen(f, 2, 'ranking', 'ja', '2026-11-28T10:00:00Z');
  const z = K.rankingZeilen(d, f);
  assert.deepStrictEqual(z.map(x => x.rang), [1, 2, 3]);
  assert.deepStrictEqual([z[0].erwartet, z[0].von, z[0].kumuliert, z[0].trend, z[0].abgehakt], [3.1, 40, 8, 'steigend', false]);
  assert.deepStrictEqual([z[1].erwartet, z[1].kumuliert, z[1].trend, z[1].abgehakt], [1.7, 12, 'fallend', true]);
  assert.deepStrictEqual([z[2].erwartet, z[2].von, z[2].kumuliert, z[2].trend, z[2].stufe], [null, null, null, null, null]);
});

test('Ranking-Haken: übersteht das Zusammenführen mit einem Stand ohne ihn, späteres Abwählen gewinnt', () => {
  const a = { fach: 'test', versuche: {}, schritte: { 4: { ranking: { wert: 'ja', zeit: '2026-11-28T10:00:00Z' } } } };
  const b = { fach: 'test', versuche: {}, schritte: { 4: { kern: { wert: 'ja', zeit: '2026-11-27T10:00:00Z' } } } };
  for (const g of [K.zusammenfuehren(a, b), K.zusammenfuehren(b, a)]) {
    assert.strictEqual(K.schrittWert(g, 4, 'ranking'), 'ja');
    assert.strictEqual(K.schrittWert(g, 4, 'kern'), 'ja');
  }
  const c = { fach: 'test', versuche: {}, schritte: { 4: { ranking: { wert: null, zeit: '2026-11-28T11:00:00Z' } } } };
  assert.strictEqual(K.schrittWert(K.zusammenfuehren(a, c), 4, 'ranking'), null);
  assert.strictEqual(K.schrittWert(K.zusammenfuehren(c, a), 4, 'ranking'), null);
});

test('Fächer: nach Klausurdatum je Semester, vergangene zuletzt', () => {
  assert.strictEqual(K.semesterVon('2027-02-12'), 'WiSe 26/27');
  assert.strictEqual(K.semesterVon('2027-07-02'), 'SoSe 27');
  assert.strictEqual(K.semesterVon('2026-12-01'), 'WiSe 26/27');
  assert.strictEqual(K.semesterVon('2000-03-01'), 'WiSe 99/00');
  const liste = [
    { name: 'Neuro', klausur: '2027-06-30' }, { name: 'Chir', klausur: '2027-06-28' },
    { name: 'MiBi', klausur: '2027-02-12' }, { name: 'Humgen', klausur: '2027-02-12' },
    { name: 'Alt', klausur: '2026-07-01' }, { name: 'Älter', klausur: '2026-02-01' },
  ];
  const g = K.faecherGruppen(liste, '2026-11-28');
  assert.deepStrictEqual(g.map(x => x.titel), ['WiSe 26/27', 'SoSe 27', 'Vorbei']);
  assert.deepStrictEqual(g.map(x => x.faecher.map(y => y.name)), [['Humgen', 'MiBi'], ['Chir', 'Neuro'], ['Alt', 'Älter']]);
  assert.deepStrictEqual(K.faecherGruppen(liste, '2027-02-12')[0].faecher.map(y => y.name), ['Humgen', 'MiBi']);
});
