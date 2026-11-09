// Bildschirme der Altfragen-App: Start, Themen, Thema mit Kern, Fragerunde, Wiederholung, Probeklausur, Einstellungen.
// Daten und Lernstand liegen im Browser (IndexedDB) und werden mit Drive abgeglichen, sobald eine Anmeldung gilt.
// Ohne Netz läuft alles weiter, der Abgleich holt nach.
(() => {
  const K = Kern;
  const M = Markdown;
  const D = Drive;
  const BEREICH = 'https://www.googleapis.com/auth/drive.file';
  const VERSION = '1.2';

  // ---------- Ablage im Browser (IndexedDB) ----------
  // Schlüssel-Wert-Speicher: konfig, fragen:<fach>, fortschritt:<fach>. Größer als localStorage erlaubt.
  const Ablage = (() => {
    let db = null;
    function oeffnen() {
      if (db) return Promise.resolve(db);
      return new Promise((fertig, fehler) => {
        const r = indexedDB.open('altfragen', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('kv');
        r.onsuccess = () => { db = r.result; fertig(db); };
        r.onerror = () => fehler(r.error);
      });
    }
    async function holen(k) {
      const d = await oeffnen();
      return new Promise((fertig, fehler) => {
        const r = d.transaction('kv').objectStore('kv').get(k);
        r.onsuccess = () => fertig(r.result === undefined ? null : r.result);
        r.onerror = () => fehler(r.error);
      });
    }
    async function setzen(k, v) {
      const d = await oeffnen();
      return new Promise((fertig, fehler) => {
        const t = d.transaction('kv', 'readwrite');
        t.objectStore('kv').put(v, k);
        t.oncomplete = () => fertig();
        t.onerror = () => fehler(t.error);
      });
    }
    // Lesen und Schreiben in einer Transaktion: mischen(alt) liefert den neuen Wert.
    // So kann ein zweiter Tab der App zwischen Lesen und Schreiben nichts überschreiben.
    async function aendern(k, mischen) {
      const d = await oeffnen();
      return new Promise((fertig, fehler) => {
        const t = d.transaction('kv', 'readwrite');
        const s = t.objectStore('kv');
        let neu;
        const r = s.get(k);
        r.onsuccess = () => { neu = mischen(r.result === undefined ? null : r.result); s.put(neu, k); };
        t.oncomplete = () => fertig(neu);
        t.onerror = () => fehler(t.error);
      });
    }
    return { holen, setzen, aendern };
  })();
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});

  // ---------- Zustand ----------
  let konfig = null;
  const faecher = {};
  const sync = { laeuft: false, nochmal: false, zeit: null, fehler: '', hinweis: '', kurz: '', lesefehler: {}, offen: false };
  let einstellungen = { rundeGroesse: 20 };
  let aktivFach = null;
  let runde = null;
  let abgleichUhr = null;
  const geraet = (() => {
    try {
      let g = localStorage.getItem('altfragen_geraet');
      if (!g) { g = Math.random().toString(36).slice(2, 10); localStorage.setItem('altfragen_geraet', g); }
      return g;
    } catch (e) { return 'g' + Math.random().toString(36).slice(2, 8); }
  })();
  const jetzt = () => new Date().toISOString();
  const heute = () => K.tagVon(Date.now());
  const fach = () => faecher[aktivFach];

  // ---------- Kleine Helfer für den Bildschirmaufbau ----------
  // el('button', {class: 'knopf', onclick: f, text: 'OK'}, kind, …) baut einen Knoten; Text immer über textContent.
  const app = document.getElementById('app');
  function el(tag, attrs = {}, ...kinder) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'text') n.textContent = v;
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else if (k === 'class') n.className = v;
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const kind of kinder.flat()) if (kind !== null && kind !== undefined && kind !== false) n.append(kind);
    return n;
  }
  const md = text => { const d = el('div', { class: 'md' }); d.append(M.zuDom(text)); return d; };
  const mdZeile = text => { const s = el('span'); s.append(M.inline(M.zeile(String(text || '')), document)); return s; };
  const knopf = (text, onclick, klasse = '') => el('button', { class: 'knopf ' + klasse, onclick, text });
  const WOCHENTAG = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  function datum(tag) {
    const d = new Date(tag + 'T12:00:00Z');
    return `${WOCHENTAG[d.getUTCDay()]} ${tag.slice(8, 10)}.${tag.slice(5, 7)}.`;
  }
  function uhrzeit(iso) {
    return new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }

  // ---------- Navigation mit Zurück-Taste ----------
  // Jeder Bildschirm ist ein Eintrag im Browserverlauf; die Zurück-Geste des Handys führt so zum vorigen.
  // Der Stapel spiegelt den Browserverlauf: Eintrag n im Verlauf = Tiefe n im Stapel (state.n).
  const stapel = [];
  let nachZurueck = null;
  // bleiben = derselbe Bildschirm wird nur aktualisiert, die Scrollposition bleibt
  function zeige(name, param = {}, ersetzen = false, bleiben = false) {
    if (ersetzen && stapel.length) stapel[stapel.length - 1] = { name, param };
    else { stapel.push({ name, param }); history.pushState({ n: stapel.length }, ''); }
    probeSichern();
    zeichnen(bleiben);
  }
  function zurueck() {
    if (stapel.length > 1) history.back();
    else zeige('start', {}, true);
  }
  // Auf Tiefe `tiefe` zurück (1 = Start), den Browserverlauf mitnehmen, danach optional `danach` ausführen
  function zurueckAuf(tiefe, danach = null) {
    const n = stapel.length - tiefe;
    if (n <= 0) { if (danach) danach(); else zeichnen(); return; }
    nachZurueck = danach;
    history.go(-n);
  }
  window.addEventListener('popstate', e => {
    // Eine laufende Probeklausur verschwindet nicht durch die Zurück-Geste
    const oben = stapel[stapel.length - 1];
    if (runde && runde.probe && !runde.probe.abgegeben && oben && oben.name === 'frage') {
      history.pushState({ n: stapel.length }, '');
      kurzHinweis('Probeklausur läuft. Abbrechen: oben links ‹ zweimal tippen');
      return;
    }
    const n = (e.state && e.state.n) || 1;
    if (n < stapel.length) stapel.length = Math.max(1, n);
    const danach = nachZurueck;
    nachZurueck = null;
    if (danach) danach(); else zeichnen();
  });
  function zeichnen(bleiben = false) {
    const s = stapel[stapel.length - 1] || { name: 'start', param: {} };
    const y = window.scrollY;
    app.replaceChildren();
    const bild = BILDER[s.name] || BILDER.start;
    app.append(...[].concat(bild(s.param)).filter(Boolean));
    window.scrollTo(0, bleiben ? y : 0);
  }

  // ---------- Laden beim Start ----------
  async function laden() {
    try {
      einstellungen = { ...einstellungen, ...JSON.parse(localStorage.getItem('altfragen_einstellungen') || '{}') };
    } catch (e) { /* Standardwerte */ }
    konfig = await Ablage.holen('konfig');
    if (konfig) {
      for (const fk of konfig.faecher) {
        const fr = await Ablage.holen('fragen:' + fk.id);
        if (!fr) continue;
        const f = (await Ablage.holen('fortschritt:' + fk.id)) || K.leererFortschritt(fk.id);
        faecher[fk.id] = { daten: fr.daten, ix: K.erschliessen(fr.daten), fortschritt: K.vervollstaendigen(f, fk.id), fragenZeit: fr.zeit };
      }
    }
    aktivFach = localStorage.getItem('altfragen_fach');
    if (!faecher[aktivFach]) aktivFach = Object.keys(faecher)[0] || null;
  }
  // Speichern mischt mit dem, was ein anderer Tab der App inzwischen gespeichert hat.
  // Danach noch einmal mit dem Speicher vereinigen, damit Antworten aus der Wartezeit bleiben.
  async function lokalSpeichern(id) {
    const fa = faecher[id];
    const gemischt = await Ablage.aendern('fortschritt:' + id, alt => K.zusammenfuehren(fa.fortschritt, alt || {}));
    fa.fortschritt = K.zusammenfuehren(gemischt, fa.fortschritt);
  }
  // Stand anderer Tabs übernehmen, etwa wenn die App wieder in den Vordergrund kommt
  async function lokalEinmischen() {
    for (const [id, fa] of Object.entries(faecher)) {
      const alt = await Ablage.holen('fortschritt:' + id);
      if (alt) fa.fortschritt = K.zusammenfuehren(fa.fortschritt, alt);
    }
  }

  // ---------- Abgleich mit Drive ----------
  // Je Fach: Fragen aktualisieren, Fortschritt von Drive holen und zusammenführen, Lernskript abgleichen,
  // dann beides hochladen. Antworten, die währenddessen dazukommen, werden am Ende erneut eingemischt.
  // Meldungen des laufenden Abgleichs sammeln sich in lauf und gehen erst am Ende in die Statuszeile,
  // damit eine bleibende Meldung währenddessen nicht verschwindet und wiederkommt
  let lauf = { fehler: '', hinweis: '' };
  async function abgleich() {
    if (sync.laeuft) { sync.nochmal = true; return; }
    if (!D.gueltig()) { statusZeichnen(); return; }
    sync.laeuft = true;
    lauf = { fehler: '', hinweis: '' };
    let neueDaten = false;
    try {
      const cfg = await D.suchen('config');
      if (!cfg.length) throw new Error('Keine App-Daten auf Drive gefunden');
      konfig = JSON.parse(await D.lesen(cfg[0].id));
      await Ablage.setzen('konfig', konfig);
      for (const fk of konfig.faecher) {
        try {
          neueDaten = (await fachAbgleichen(fk)) || neueDaten;
        } catch (e) {
          lauf.fehler = `${fk.name}: ${e.message}`;
          if (e.code === 401) break;
        }
      }
      if (!faecher[aktivFach]) aktivFach = Object.keys(faecher)[0] || null;
      if (!lauf.fehler) { sync.zeit = jetzt(); sync.offen = false; }
    } catch (e) {
      lauf.fehler = e.message;
    } finally {
      sync.fehler = lauf.fehler;
      sync.hinweis = lauf.hinweis;
      sync.laeuft = false;
      const s = stapel[stapel.length - 1];
      // Nur Übersichten neu zeichnen, an der Stelle, an der man steht; in Thema und Frage nur die Statuszeile
      if (neueDaten && (!s || ['start', 'themen'].includes(s.name))) zeichnen(true);
      else statusZeichnen();
      if (sync.nochmal) { sync.nochmal = false; setTimeout(abgleich, 300); }
    }
  }

  // Reihenfolge wie in FORMAT.md, Abschnitt Schutz: erst der Fortschritt, dann die .md, dann wieder der Fortschritt.
  async function fachAbgleichen(fk) {
    let neu = false;
    let fa = faecher[fk.id];
    const meta = await D.metadaten(fk.fragen);
    if (!fa || fa.fragenZeit !== meta.modifiedTime) {
      const daten = JSON.parse(await D.lesen(fk.fragen));
      if (!fa) {
        const f = (await Ablage.holen('fortschritt:' + fk.id)) || K.leererFortschritt(fk.id);
        fa = faecher[fk.id] = { fortschritt: K.vervollstaendigen(f, fk.id) };
      }
      // Dasselbe Objekt behalten, damit offene Bildschirme weiter auf den aktuellen Stand zeigen
      Object.assign(fa, { daten, ix: K.erschliessen(daten), fragenZeit: meta.modifiedTime });
      await Ablage.setzen('fragen:' + fk.id, { daten, zeit: meta.modifiedTime });
      neu = true;
    }
    // 1. Fortschritt von Drive. Leer oder unlesbar: anhalten, sonst könnte ein alter Stand gewinnen
    const fernText = await D.lesen(fk.fortschritt);
    if (!fernText.trim()) throw new Error('Fortschritt auf Drive ist leer, Abgleich ausgesetzt');
    const fern = JSON.parse(fernText);
    const vorher = JSON.stringify(fa.fortschritt.versuche);
    // 2. Zusammenführen und hochladen, bevor die .md angefasst wird
    await hochladen(fk, K.zusammenfuehren(fa.fortschritt, fern));
    // 3. Lernskript abgleichen. Hat Docs zwischen Lesen und Schreiben gespeichert, von vorn (höchstens dreimal)
    if (fk.lernskript) {
      for (let versuch = 0; versuch < 3; versuch++) {
        const mm = await D.metadaten(fk.lernskript);
        const text = await D.lesen(fk.lernskript);
        const r = K.abgleichen(fa.fortschritt, text, mm.modifiedTime, fa.ix, jetzt());
        sync.lesefehler[fk.id] = r.fehler;
        if (r.abbruch) lauf.hinweis = `${fk.name}: ${r.abbruch}`;
        const f = r.fortschritt;
        if (r.mdNeu !== null) {
          const kurz = await D.metadaten(fk.lernskript);
          if (kurz.modifiedTime !== mm.modifiedTime) continue;
          try {
            await D.schreiben(fk.lernskript, r.mdNeu, 'text/markdown');
          } catch (e) {
            f.md = r.mdAlt;
            lauf.fehler = `${fk.name}: Lernskript nicht geschrieben (${e.message})`;
          }
        }
        await hochladen(fk, f);
        break;
      }
    }
    return neu || JSON.stringify(fa.fortschritt.versuche) !== vorher;
  }
  // Fortschritt hochladen und in den Speicher übernehmen. Die Vereinigung mit dem aktuellen Speicher läuft
  // ohne Unterbrechung, deshalb bleiben Antworten erhalten, die während des Hochladens dazukamen.
  async function hochladen(fk, f) {
    await D.schreiben(fk.fortschritt, JSON.stringify(f), 'application/json');
    const fa = faecher[fk.id];
    fa.fortschritt = K.zusammenfuehren(f, fa.fortschritt);
    await lokalSpeichern(fk.id);
  }

  // Nach einer Antwort nicht sofort, sondern gebündelt abgleichen; beim Verlassen der App sofort.
  function abgleichPlanen() {
    sync.offen = true;
    statusZeichnen();
    clearTimeout(abgleichUhr);
    abgleichUhr = setTimeout(abgleich, 20000);
  }
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'hidden' && sync.offen && D.gueltig()) { clearTimeout(abgleichUhr); abgleich(); }
    if (document.visibilityState === 'visible') {
      await lokalEinmischen();
      const s = stapel[stapel.length - 1];
      if (s && ['start', 'themen'].includes(s.name)) zeichnen(true);
      if (D.gueltig() && !sync.laeuft) abgleich();
    }
  });
  // Kommt die Anmeldung erst nach einer Fehlmeldung des Google-Fensters an, trotzdem abgleichen
  D.beiAnmeldung(() => { statusZeichnen(); abgleich(); });

  // Abgelaufene Anmeldung beim nächsten Tippen irgendwo in der App still erneuern, statt auf „Verbinden“ zu warten.
  // Google öffnet dabei kurz ein Fenster, das sich selbst schließt; Browser erlauben das nur direkt nach einer
  // Berührung. Nur mit gemerktem Konto, mit Netz und höchstens alle zehn Minuten, damit ein Fehlschlag nicht bei
  // jedem Tipp kommt. Nicht auf Knöpfen, die selbst anmelden (data-anmeldung), und nicht in den Einstellungen,
  // wo Abmelden liegt. true = Auffangphase: läuft vor dem eigentlichen Klick, der danach normal weiterwirkt.
  let stillVersucht = 0;
  document.addEventListener('click', e => {
    if (D.gueltig() || !D.kannStillErneuern() || !navigator.onLine || Date.now() - stillVersucht < 10 * 60000) return;
    if (e.target && e.target.closest && e.target.closest('[data-anmeldung]')) return;
    const s = stapel[stapel.length - 1];
    if (s && s.name === 'einstellungen') return;
    stillVersucht = Date.now();
    D.anmelden().then(() => abgleich()).catch(() => statusZeichnen());
  }, true);

  // Ausdrücklich verbinden: immer eine neue Anfrage an Google, auch wenn eine ältere liegen geblieben ist
  async function verbinden() {
    try {
      await D.vorbereiten(KONFIG.clientId, BEREICH);
      await D.anmelden(true);
      await abgleich();
    } catch (e) {
      sync.fehler = e.message;
      statusZeichnen();
    }
  }
  const verbindenKnopf = (text, klasse) => el('button', { class: klasse, onclick: verbinden, 'data-anmeldung': true, text });

  // Statuszeile unten. Ruhig: Ein laufender oder geplanter Abgleich ändert den Text nicht, er zeigt bis zum Ende
  // den letzten Stand. Laut wird sie nur bei Fehler oder fehlender Verbindung.
  // modus 'leise' (Fragen): nur Fehler, Hinweise und fehlende Verbindung, sonst leer.
  function statusZeile(modus = '') {
    const z = el('div', { class: 'status', id: 'status', 'data-modus': modus || null });
    if (!D.gueltig() && !sync.laeuft) z.append(el('span', { text: sync.offen ? 'Neue Antworten liegen nur auf dem Gerät. ' : 'Nicht mit Drive verbunden. ' }), verbindenKnopf('Verbinden', 'verweis'));
    else if (sync.fehler) z.append(el('span', { class: 'rot', text: sync.fehler + ' ' }), el('button', { class: 'verweis', onclick: abgleich, text: 'Erneut' }));
    else if (modus !== 'leise') z.append(sync.zeit ? `Abgeglichen ${uhrzeit(sync.zeit)}` : 'Mit Drive verbunden');
    if (sync.hinweis) z.append(el('div', { class: 'rot', text: sync.hinweis }));
    if (sync.kurz) z.append(el('div', { class: 'rot', text: sync.kurz }));
    return z;
  }
  // Kurzer Hinweis für drei Sekunden in der Statuszeile, getrennt von Meldungen des Abgleichs
  let kurzUhr = null;
  function kurzHinweis(text) {
    sync.kurz = text;
    statusZeichnen();
    clearTimeout(kurzUhr);
    kurzUhr = setTimeout(() => { sync.kurz = ''; statusZeichnen(); }, 3000);
  }
  // Nur ersetzen, wenn sich der Inhalt ändert, damit nichts flackert
  function statusZeichnen() {
    const alt = document.getElementById('status');
    if (!alt) return;
    const neu = statusZeile(alt.dataset.modus || '');
    if (neu.innerHTML !== alt.innerHTML) alt.replaceWith(neu);
  }

  // ---------- Bildschirm: Anmeldung ----------
  function bildAnmelden() {
    return [
      el('h1', { text: 'Altfragen' }),
      el('p', { class: 'unter', text: 'Fragen und Lernstand liegen auf deinem Google Drive. Nach der Anmeldung läuft die App auch ohne Netz.' }),
      verbindenKnopf('Mit Google anmelden', 'knopf haupt'),
      sync.laeuft || sync.fehler ? statusZeile() : el('div', { id: 'status' }),
    ];
  }

  // ---------- Bildschirm: Start ----------
  function bildStart() {
    if (!aktivFach) return bildAnmelden();
    const fa = fach();
    const d = fa.daten;
    const f = fa.fortschritt;
    const h = heute();
    const tp = K.tempo(d, f, h);
    const due = K.faellige(d, f, h);
    const weiter = K.naechstesThema(d, f, h);
    const teile = [el('h1', { text: 'Altfragen' })];
    if (Object.keys(faecher).length > 1) {
      teile.push(el('div', { class: 'segment' }, ...Object.values(faecher).map(x => el('button', {
        class: 'knopf' + (x.daten.fach === aktivFach ? ' an' : ''),
        onclick: () => { aktivFach = x.daten.fach; localStorage.setItem('altfragen_fach', aktivFach); zeige('start', {}, true); },
        text: x.daten.name,
      }))));
    }
    teile.push(el('p', { class: 'unter', text: `Klausur ${datum(d.klausur)} · noch ${tp.bisKlausur} Tage · ${d.klausurInfo}` }));

    // Wiederholen
    const wk = el('section', { class: 'karte' }, el('h2', { text: 'Wiederholen' }));
    if (due.length) {
      const n = Math.min(due.length, einstellungen.rundeGroesse);
      wk.append(el('p', { text: `${due.length} fällig` + (due.length > n ? `, diese Runde ${n}` : '') }));
      wk.append(knopf('Wiederholen', () => rundeStarten('wiederholen', due.slice(0, n).map(x => x.frage.id)), 'haupt'));
    } else {
      const n = K.naechsteFaelligkeit(d, f, h);
      wk.append(el('p', { class: 'unter', text: n ? `Nichts fällig. Nächste am ${datum(n)}` : 'Nichts fällig' }));
    }
    teile.push(wk);

    // Weiter im Plan
    const pk = el('section', { class: 'karte' }, el('h2', { text: 'Weiter im Plan' }));
    if (weiter) {
      const t = weiter.thema;
      const st = weiter.stand;
      pk.append(el('p', {}, el('strong', { text: `${t.rang} · ` }), t.titel, weiter.optional ? el('span', { class: 'unter', text: ' · nur bei Zeit' }) : null));
      pk.append(schritteZeile(st));
      const naechster = !st.meditricks || !st.kern ? 'Zum Thema' : (st.naechste ? `Weiter mit Frage ${st.naechste.nr}` : 'Zum Thema');
      pk.append(knopf(naechster, () => {
        if (st.meditricks && st.kern && st.naechste) themaRunde(t, 'weiter');
        else zeige('thema', { rang: t.rang });
      }, 'haupt'));
    } else {
      pk.append(el('p', { text: 'Erster Durchgang fertig. Probeklausur, dann Wiederholung.' }));
    }
    pk.append(el('p', { class: 'unter klein', text: tp.offen ? `Erster Durchgang bis ${datum(tp.ziel)}: ${tp.offen} Fragen offen, etwa ${tp.proTag} pro Tag` : `Erster Durchgang vollständig` }));
    teile.push(pk);

    // Fehlersammlung: alles, was je falsch oder unsicher war, bleibt hier, auch wenn es inzwischen sitzt
    const fs = K.fehlerSammlung(d, f);
    if (fs.length) {
      const n = Math.min(fs.length, einstellungen.rundeGroesse);
      teile.push(el('section', { class: 'karte' }, el('h2', { text: 'Fehlersammlung' }),
        el('p', { text: `${fs.length} Fragen, die du je falsch oder unsicher hattest` + (fs.length > n ? `, diese Runde ${n}` : '') }),
        el('p', { class: 'unter klein0', text: 'Bleiben drin, auch wenn sie später sitzen.' }),
        knopf('Durchgehen', () => rundeStarten('fehler', fs.slice(0, n).map(x => x.frage.id)))));
    }

    teile.push(el('div', { class: 'leiste' },
      knopf('Themen', () => zeige('themen')),
      knopf('Probeklausur', () => zeige('probe-wahl')),
      knopf('Einstellungen', () => zeige('einstellungen'))));
    teile.push(statusZeile());
    return teile;
  }

  function schritteZeile(st) {
    const chip = (an, text) => el('span', { class: 'chip' + (an ? ' an' : '') , text: (an ? '✓ ' : '') + text });
    return el('div', { class: 'chips' },
      chip(!!st.meditricks, st.meditricks === 'keins' ? 'kein Meditricks' : 'Meditricks'),
      chip(!!st.kern, 'Kern'),
      chip(st.beantwortet === st.gesamt, `Fragen ${st.beantwortet}/${st.gesamt}`),
      st.faellig || st.wartet ? chip(false, `Wiederholung ${st.faellig + st.wartet}`) : null);
  }

  // ---------- Bildschirm: Themen ----------
  function bildThemen() {
    const fa = fach();
    const d = fa.daten;
    const h = heute();
    const teile = [kopf(d.name + ': Themen')];
    let block = undefined;
    let optional = false;
    for (const p of K.planListe(d)) {
      const t = p.thema;
      if (p.optional && !optional) { optional = true; teile.push(el('h3', { text: 'Stufe C, nur bei Zeit' })); }
      if (!p.optional && d.plan === 'block-stufe' && t.block !== block) {
        block = t.block;
        const b = d.bloecke.find(x => x.nr === block);
        teile.push(el('h3', { text: b ? `Block ${b.nr} · ${b.titel}` : 'Weitere' }));
      }
      const st = K.themaStand(t, fa.fortschritt, h, d.klausur);
      const anteil = st.gesamt ? st.beantwortet / st.gesamt : 0;
      const info = [`${st.beantwortet}/${st.gesamt}`];
      if (st.beantwortet) info.push(`${Math.round(100 * st.richtig / st.beantwortet)} % sicher`);
      if (st.faellig) info.push(`${st.faellig} fällig`);
      // Breite über das style-Objekt: Die CSP der Seite verbietet style-Attribute im Markup
      const wert = el('span', { class: 'balken-wert' });
      wert.style.width = `${Math.round(anteil * 100)}%`;
      teile.push(el('button', { class: 'balken' + (st.fertig ? ' fertig' : ''), onclick: () => zeige('thema', { rang: t.rang }) },
        el('span', { class: 'balken-name' }, el('strong', { text: `${t.rang} ` }), t.titel, t.stufe ? el('span', { class: 'unter', text: ` · ${t.stufe}` }) : null),
        el('span', { class: 'balken-zahl', text: info.join(' · ') }),
        el('span', { class: 'balken-spur' }, wert)));
    }
    teile.push(statusZeile());
    return teile;
  }

  function kopf(titel) {
    return el('div', { class: 'kopf' }, el('button', { class: 'zurueck', onclick: zurueck, 'aria-label': 'Zurück', text: '‹' }), el('h2', { text: titel }));
  }

  // ---------- Bildschirm: Thema ----------
  function bildThema({ rang }) {
    const fa = fach();
    const t = fa.ix.themen.get(rang);
    if (!t) return bildStart();
    const f = fa.fortschritt;
    const st = K.themaStand(t, f, heute(), fa.daten.klausur);
    // Den Fortschritt erst beim Tippen holen: Ein Abgleich im Hintergrund kann ihn inzwischen ersetzt haben
    const setze = (feld, wert) => { K.schrittSetzen(fach().fortschritt, rang, feld, wert, jetzt()); lokalSpeichern(aktivFach); abgleichPlanen(); zeige('thema', { rang }, true, true); };
    const teile = [kopf(`${t.rang} · ${t.titel}`)];
    teile.push(el('p', { class: 'unter', text: [t.stufe ? `Stufe ${t.stufe}` : null, t.meta].filter(Boolean).join(' · ') }));
    teile.push(schritteZeile(st));

    // 1 Meditricks
    teile.push(el('section', { class: 'karte' }, el('h3', { text: '1 · Meditricks zum Thema, ganz' }),
      st.meditricks
        ? el('div', { class: 'leiste' }, el('p', { class: 'gruen', text: st.meditricks === 'keins' ? 'Gibt es nicht' : 'Gesehen' }), knopf('Zurücksetzen', () => setze('meditricks', null), 'leise'))
        : el('div', { class: 'leiste' }, knopf('Gesehen', () => setze('meditricks', 'ja')), knopf('Gibt es nicht', () => setze('meditricks', 'keins')))));

    // 2 Kern
    const kern = el('section', { class: 'karte' }, el('h3', { text: '2 · Kern' }), md(t.kern));
    if (t.falle) kern.append(el('p', {}, el('strong', { text: 'Falle: ' }), mdZeile(t.falle)));
    if (t.tabellen) kern.append(md(t.tabellen));
    for (const a of t.abschnitte || []) kern.append(el('details', { class: 'mehr' }, el('summary', { text: a.titel }), md(a.text)));
    if (t.gefragt && t.gefragt.length) kern.append(el('details', { class: 'mehr' }, el('summary', { text: 'So wurde gefragt' }), md(t.gefragt.map(g => (/^\s*[-*] /.test(g) ? g : '- ' + g)).join('\n'))));
    kern.append(st.kern
      ? el('div', { class: 'leiste' }, el('p', { class: 'gruen', text: 'Gelesen' }), knopf('Zurücksetzen', () => setze('kern', null), 'leise'))
      : knopf('Kern gelesen', () => setze('kern', 'ja')));
    teile.push(kern);

    // 3 Fragen
    const fr = el('section', { class: 'karte' }, el('h3', { text: `3 · Fragen: ${st.beantwortet} von ${st.gesamt}` }));
    if (st.naechste) fr.append(knopf(st.beantwortet ? `Weiter mit Frage ${st.naechste.nr}` : 'Fragen starten', () => themaRunde(t, 'weiter'), 'haupt'));
    // Je falsch oder unsicher, wie in der Fehlersammlung der Startseite
    const schwach = K.fehlerSammlung(fa.daten, f).filter(x => x.thema.rang === t.rang);
    if (schwach.length) fr.append(knopf(`Je falsch oder unsicher (${schwach.length})`, () => themaRunde(t, 'schwach')));
    if (st.beantwortet) fr.append(knopf('Alle von vorn', () => themaRunde(t, 'alle'), 'leise'));
    fr.append(el('p', { class: 'unter klein', text: 'Danach, wo es noch hakt: der passende Amboss-Abschnitt. Falsche und unsichere kommen nach zwei bis drei Tagen wieder.' }));
    const ls = lernskriptId();
    if (ls) fr.append(el('a', { class: 'verweis klein', href: `https://docs.google.com/document/d/${encodeURIComponent(ls)}/edit?rtpof=true`, target: '_blank', rel: 'noopener', text: 'Lernskript in Google Docs öffnen' }));
    teile.push(fr);
    teile.push(statusZeile());
    return teile;
  }

  function lernskriptId() {
    const fk = konfig && konfig.faecher.find(x => x.id === aktivFach);
    return fk ? fk.lernskript : null;
  }

  // ---------- Fragerunden ----------
  // runde = {art, liste: [Frage-IDs], pos, versuch: {id: Versuch-ID}, wahl: {id: [Texte]}, mischen, probe}
  function themaRunde(t, wie) {
    const fa = fach();
    const qs = t.fragen.filter(q => q.typ !== 'fragment' || wie === 'alle' || wie === 'weiter');
    let liste = qs;
    let pos = 0;
    if (wie === 'weiter') {
      const i = qs.findIndex(q => q.typ !== 'fragment' && K.wiederholung(q, fa.fortschritt.versuche[q.id], heute(), fa.daten.klausur).status === 'neu');
      pos = Math.max(0, i);
    }
    if (wie === 'schwach') {
      // Fehlersammlung dieses Themas: je falsch oder unsicher, in Reihenfolge des Themas
      const drin = new Set(K.fehlerSammlung(fa.daten, fa.fortschritt).filter(x => x.thema.rang === t.rang).map(x => x.frage.id));
      liste = qs.filter(q => drin.has(q.id));
    }
    rundeStarten(wie === 'schwach' ? 'wiederholen' : 'thema', liste.map(q => q.id), pos, t.rang);
  }

  function rundeStarten(art, liste, pos = 0, rang = null, probe = null) {
    if (!liste.length) return;
    runde = { art, liste, pos, rang, versuch: {}, auswahl: {}, aufgedeckt: {}, samen: {}, mischen: art !== 'thema', probe, start: jetzt() };
    zeige('frage');
  }

  // Startwert fürs Mischen je Frage einmal pro Runde festlegen, damit sich die Reihenfolge nach dem Antworten nicht ändert
  function optionenFuer(q) {
    if (!runde.mischen) return q.optionen;
    if (!(q.id in runde.samen)) runde.samen[q.id] = runde.probe ? runde.probe.name : String(K.gueltige(fach().fortschritt.versuche[q.id]).length);
    return K.mischen(q.optionen, `${q.id}:${runde.samen[q.id]}`);
  }

  // Laufende Probeklausur sichern, damit sie übersteht, wenn Android die App im Hintergrund beendet
  const PROBE_MERKER = 'altfragen_probe';
  function probeSichern() {
    try {
      if (runde && runde.probe && !runde.probe.abgegeben) localStorage.setItem(PROBE_MERKER, JSON.stringify({ fach: aktivFach, runde }));
      else localStorage.removeItem(PROBE_MERKER);
    } catch (e) { /* ohne Speicher geht die Probe beim Beenden verloren */ }
  }
  function probeWiederherstellen() {
    try {
      const g = JSON.parse(localStorage.getItem(PROBE_MERKER) || 'null');
      if (!g || !faecher[g.fach]) return false;
      aktivFach = g.fach;
      runde = g.runde;
      return true;
    } catch (e) { return false; }
  }

  function bildFrage() {
    if (!runde) return bildStart();
    const fa = fach();
    const id = runde.liste[runde.pos];
    const eintrag = fa.ix.fragen.get(id);
    if (!eintrag) return bildStart();
    const { frage: q, thema: t } = eintrag;
    const f = fa.fortschritt;
    const vid = runde.versuch[id];
    const v = vid ? (f.versuche[id] || []).find(x => x.id === vid && !x.geloescht) : null;
    const probe = !!runde.probe;
    const teile = [];
    const kopfText = probe ? `${runde.probe.name} · ${runde.pos + 1} von ${runde.liste.length}` : `${t.rang} · Frage ${q.nr}` + (runde.art === 'thema' ? ` von ${t.fragen.length}` : ` · ${runde.pos + 1}/${runde.liste.length}`);
    teile.push(el('div', { class: 'kopf' }, el('button', { class: 'zurueck', onclick: rundeVerlassen, 'aria-label': 'Runde verlassen', text: '‹' }),
      el('div', {}, el('div', { class: 'marke', text: kopfText }), probe ? null : el('div', { class: 'unter klein0', text: t.titel }))));
    if (probe) teile.push(probeUhr());
    if (q.mal > 1 && !probe) teile.push(el('div', { class: 'marke', text: `${q.mal}× gefragt` }));
    teile.push(el('p', { class: 'stamm' }, mdZeile(q.stamm)));
    if (q.aussagen) teile.push(el('ol', { class: 'aussagen' }, ...q.aussagen.map(a => el('li', {}, mdZeile(a)))));

    if (q.typ === 'fragment') {
      teile.push(el('div', { class: 'karte' }, el('p', { text: 'Lösung nicht überliefert' }), q.loesung && q.loesung.w ? el('p', { class: 'unter' }, mdZeile(q.loesung.w)) : null));
      teile.push(weiterLeiste(true));
      return teile;
    }
    if (q.typ === 'offen' || !q.optionen.length) {
      teile.push(...offeneFrage(q, v, id));
      return teile;
    }

    const opts = optionenFuer(q);
    const mehrere = q.optionen.filter(o => o.richtig).length > 1;
    // Nach dem Abgeben einer Probeklausur Lösung auch bei übersprungenen Fragen zeigen
    const geloest = probe ? runde.probe.abgegeben : !!v;
    const auswahl = runde.auswahl[id] || (runde.auswahl[id] = []);
    if (mehrere && !geloest) teile.push(el('p', { class: 'unter', text: 'Mehrere Antworten richtig' }));
    const liste = el('div', { class: 'wahl' });
    for (const o of opts) {
      let klasse = 'knopf option';
      const gewaehlt = (v ? v.wahl : auswahl).some(x => K.normal(x) === K.normal(o.t));
      if (geloest) {
        if (o.richtig) klasse += ' richtig';
        else if (gewaehlt) klasse += ' daneben';
        else klasse += ' blass';
      } else if (gewaehlt) klasse += ' gewaehlt';
      // Nach dem Lösen steht die Begründung direkt unter der Option
      if (geloest && o.erg) klasse += ' mit-e';
      liste.append(el('button', { class: klasse, disabled: geloest || null, onclick: () => tippen(q, o, mehrere) },
        el('span', { class: 'opt-text' }, mdZeile(o.t)), geloest ? grundZeile(q, o) : null, geloest && o.erg ? ergMarke() : null));
    }
    teile.push(liste);
    if (!geloest && (mehrere || probe)) {
      if (mehrere && !probe) teile.push(knopf('Prüfen', () => antworten(q, auswahl), 'haupt' + (auswahl.length ? '' : ' aus')));
    }
    if (geloest) teile.push(...loesung(q, v));
    teile.push(weiterLeiste(geloest || probe));
    teile.push(statusZeile('leise'));
    return teile;
  }

  function tippen(q, o, mehrere) {
    const id = q.id;
    const auswahl = runde.auswahl[id] || (runde.auswahl[id] = []);
    if (mehrere) {
      const i = auswahl.findIndex(x => K.normal(x) === K.normal(o.t));
      if (i >= 0) auswahl.splice(i, 1); else auswahl.push(o.t);
      zeige('frage', {}, true, true);
      return;
    }
    if (runde.probe) { runde.auswahl[id] = [o.t]; zeige('frage', {}, true, true); return; }
    antworten(q, [o.t]);
  }

  // Antwort buchen: ein Versuch mit Quelle app, danach Lösung zeigen und den Abgleich planen.
  function antworten(q, wahl, merkmale = {}) {
    if (!wahl.length && !(q.typ === 'offen' || !q.optionen.length)) return;
    const fa = fach();
    const v = K.versuchBuchen(fa.fortschritt, q.id, { wahl, ...merkmale }, jetzt(), geraet, runde.probe ? 'probe' : 'app');
    runde.versuch[q.id] = v.id;
    lokalSpeichern(fa.daten.fach);
    abgleichPlanen();
    zeige('frage', {}, true, true);
  }

  function offeneFrage(q, v, id) {
    const teile = [el('p', { class: 'unter', text: 'Ohne Optionen überliefert: erst selbst beantworten.' })];
    if (!runde.aufgedeckt[id] && !v) {
      teile.push(knopf('Lösung zeigen', () => { runde.aufgedeckt[id] = true; zeige('frage', {}, true, true); }, 'haupt'));
      teile.push(weiterLeiste(false));
      return teile;
    }
    teile.push(el('div', { class: 'karte' }, el('p', {}, el('strong', { text: 'Lösung: ' }), mdZeile(q.loesung ? q.loesung.t : '')),
      q.loesung && q.loesung.w ? el('p', { class: 'unter' }, mdZeile(q.loesung.w)) : null));
    if (!v) {
      teile.push(el('div', { class: 'leiste' },
        knopf('Gewusst', () => antworten(q, [], {}), 'gut-knopf'),
        knopf('Unsicher', () => antworten(q, [], { unsicher: true })),
        knopf('Falsch', () => antworten(q, [], { falsch: true }), 'schlecht-knopf')));
    } else {
      const e = K.ergebnis(q, v);
      teile.push(el('p', { class: 'urteil ' + (e === 'richtig' ? 'gut' : 'schlecht'), text: e === 'richtig' ? 'Gewusst' : e === 'unsicher' ? 'Unsicher' : 'Falsch' }));
      teile.push(...zusatz(q));
    }
    teile.push(weiterLeiste(!!v));
    return teile;
  }

  // Begründung unter einer Option: ✓ trifft zu / ✗ trifft nicht zu, dahinter der Grund.
  // Ohne Grund nur bei negativ gestellten Fragen, weil dort grün (anzukreuzen) nicht „trifft zu“ heißt.
  function grundZeile(q, o) {
    const neg = q.typ === 'negativ';
    const trifft = neg ? !o.richtig : o.richtig;
    if (!o.w && !neg) return null;
    return el('span', { class: 'grund' },
      el('span', { class: 'zeichen ' + (trifft ? 'zu' : 'nicht'), text: trifft ? '✓ ' : '✗ ' }),
      o.w ? mdZeile(o.w) : (trifft ? 'trifft zu' : 'trifft nicht zu'));
  }
  // Kleines E unten rechts: Option nicht aus dem Protokoll, ergänzt. Erst nach dem Lösen, sonst verrät es Falsche
  const ergMarke = () => el('span', { class: 'erg-marke', title: 'ergänzt, nicht im Protokoll', 'aria-label': 'ergänzt', text: 'E' });

  // Lösung: Urteil, unsicher-Schalter, Extra-Fakten. Die Begründungen stehen schon an den Optionen.
  function loesung(q, v) {
    const e = v ? K.ergebnis(q, v) : null;
    const urteil = !e ? 'Nicht beantwortet' : e === 'falsch' ? 'Falsch' : (e === 'unsicher' ? 'Richtig, unsicher' : 'Richtig');
    const teile = [el('p', { class: 'urteil ' + (e === 'richtig' || e === 'unsicher' ? 'gut' : 'schlecht'), text: urteil })];
    if (e === 'richtig' || e === 'unsicher') {
      // Versuch und Fortschritt erst beim Tippen holen, ein Abgleich kann beides inzwischen erneuert haben
      teile.push(el('button', { class: 'knopf haken' + (v.unsicher ? ' an' : ''), onclick: () => {
        const f = fach().fortschritt;
        const aktuell = (f.versuche[q.id] || []).find(x => x.id === v.id);
        if (aktuell) K.versuchAendern(f, q.id, v.id, { unsicher: !aktuell.unsicher }, jetzt());
        lokalSpeichern(aktivFach); abgleichPlanen(); zeige('frage', {}, true, true);
      }, text: (v.unsicher ? '☑' : '☐') + ' unsicher (richtig, aber geraten)' }));
    }
    teile.push(...zusatz(q));
    return teile;
  }

  function zusatz(q) {
    const teile = [];
    if ((q.neu || []).length) {
      teile.push(el('div', { class: 'extra' }, el('strong', { text: 'Extra-Fakten' }), el('ul', {}, ...q.neu.map(n => el('li', {}, mdZeile(n))))));
    }
    for (const h of q.hinweis || []) teile.push(el('p', { class: 'hinweis' }, el('strong', { text: 'Hinweis: ' }), mdZeile(h)));
    if (q.ids) teile.push(el('p', { class: 'unter klein', text: q.ids }));
    return teile;
  }

  function weiterLeiste(weiterFrei) {
    const id = runde.liste[runde.pos];
    const vid = runde.versuch[id];
    const leiste = el('div', { class: 'leiste unten' });
    leiste.append(knopf('‹ Zurück', () => { if (runde.pos > 0) { runde.pos -= 1; zeige('frage', {}, true); } }, 'leise' + (runde.pos > 0 ? '' : ' aus')));
    if (vid && (!runde.probe || runde.probe.abgegeben) && runde.art !== 'probe') {
      leiste.append(knopf('Antwort zurücknehmen', () => {
        K.versuchZuruecknehmen(fach().fortschritt, id, vid, jetzt());
        delete runde.versuch[id]; runde.auswahl[id] = []; delete runde.aufgedeckt[id];
        lokalSpeichern(aktivFach); abgleichPlanen(); zeige('frage', {}, true, true);
      }, 'leise'));
    }
    const letzte = runde.pos >= runde.liste.length - 1;
    const abgeben = runde.probe && !runde.probe.abgegeben && letzte;
    const text = abgeben ? 'Abgeben' : (letzte ? 'Fertig' : 'Weiter ›');
    leiste.append(knopf(text, () => {
      if (abgeben) { probeAbgeben(); return; }
      if (letzte) { zeige('runde-ende', {}, true); return; }
      runde.pos += 1;
      zeige('frage', {}, true);
    }, weiterFrei ? 'haupt' : ''));
    return leiste;
  }

  // Runde verlassen: Thema und Wiederholung zur Zusammenfassung. Eine laufende Probeklausur wird nach
  // Rückfrage ohne Wertung abgebrochen, zurück zur Auswahl.
  function rundeVerlassen() {
    if (runde && runde.probe && !runde.probe.abgegeben) {
      if (!bestaetigen('Probeklausur abbrechen? Die Antworten werden nicht gewertet. Zum Bestätigen noch einmal tippen.')) return;
      runde = null;
      probeSichern();
      zurueckAuf(stapel.length - 1);
      return;
    }
    zeige('runde-ende', {}, true);
  }
  // Rückfrage ohne Browserdialog: zweimal tippen innerhalb von drei Sekunden
  let bestaetigt = 0;
  function bestaetigen(text) {
    if (Date.now() - bestaetigt < 3000) return true;
    bestaetigt = Date.now();
    kurzHinweis(text);
    return false;
  }

  function bildRundeEnde() {
    if (!runde) return bildStart();
    const fa = fach();
    const zahl = { richtig: 0, unsicher: 0, falsch: 0 };
    for (const [id, vid] of Object.entries(runde.versuch)) {
      const e = fa.ix.fragen.get(id);
      const v = (fa.fortschritt.versuche[id] || []).find(x => x.id === vid && !x.geloescht);
      if (e && v) { const r = K.ergebnis(e.frage, v); if (r) zahl[r] += 1; }
    }
    const n = zahl.richtig + zahl.unsicher + zahl.falsch;
    const teile = [kopfOhneZurueck(runde.probe ? runde.probe.name : 'Runde beendet')];
    if (runde.probe) {
      const soll = Math.ceil(runde.liste.length * 0.6);
      teile.push(el('p', { class: 'urteil ' + (zahl.richtig + zahl.unsicher >= soll ? 'gut' : 'schlecht'), text: `${zahl.richtig + zahl.unsicher} von ${runde.liste.length} richtig, bestanden ab ${soll}` }));
    }
    teile.push(el('p', { text: `${n} beantwortet · ${zahl.richtig} sicher richtig · ${zahl.unsicher} unsicher · ${zahl.falsch} falsch` }));
    if (zahl.falsch + zahl.unsicher) teile.push(el('p', { class: 'unter', text: 'Falsche kommen nach zwei Tagen wieder, unsichere nach drei.' }));
    if (runde.probe) teile.push(knopf('Lösungen ansehen', () => { runde.pos = 0; zeige('frage', {}, true); }));
    const rang = runde.rang;
    // Zurück über den Browserverlauf, damit die Zurück-Geste danach nicht ins Leere läuft
    if (rang) {
      teile.push(knopf('Zum Thema', () => {
        runde = null;
        const i = stapel.findIndex(s => s.name === 'thema' && s.param.rang === rang);
        if (i >= 0) zurueckAuf(i + 1); else zurueckAuf(1, () => zeige('thema', { rang }));
      }, 'haupt'));
    }
    teile.push(knopf('Zur Startseite', () => { runde = null; zurueckAuf(1); }, rang ? '' : 'haupt'));
    teile.push(statusZeile());
    return teile;
  }
  function kopfOhneZurueck(titel) {
    return el('h2', { text: titel });
  }

  // ---------- Probeklausur ----------
  function bildProbeWahl() {
    const d = fach().daten;
    const teile = [kopf('Probeklausur')];
    teile.push(el('p', { class: 'unter', text: 'Wie die echte Klausur: Antworten ohne Lösung, Zeit läuft, ausgewertet wird am Ende. Nach dem ersten Durchgang Probeklausur 1, in der letzten Woche Probeklausur 2.' }));
    for (const p of d.probeklausuren || []) {
      teile.push(knopf(`${p.name} · ${p.fragen.length} Fragen · ${p.minuten} Minuten`, () => {
        rundeStarten('probe', p.fragen, 0, null, { name: p.name, ende: Date.now() + p.minuten * 60000, abgegeben: false });
      }));
    }
    if (!(d.probeklausuren || []).length) teile.push(el('p', { text: 'Für dieses Fach gibt es keine Probeklausur.' }));
    return teile;
  }
  function probeUhr() {
    const u = el('div', { class: 'uhr' });
    const stellen = () => {
      if (!runde || !runde.probe) return;
      if (runde.probe.abgegeben) { u.textContent = 'Lösungen'; return; }
      const rest = Math.max(0, runde.probe.ende - Date.now());
      u.textContent = `${Math.floor(rest / 60000)}:${String(Math.floor(rest / 1000) % 60).padStart(2, '0')} übrig`;
      // Zeit um: abgeben wie in der echten Klausur
      if (rest === 0) setTimeout(probeAbgeben, 0);
    };
    stellen();
    clearInterval(probeUhr.takt);
    probeUhr.takt = setInterval(() => { if (!document.body.contains(u)) { clearInterval(probeUhr.takt); return; } stellen(); }, 1000);
    return u;
  }
  // Abgeben: jede angehakte Antwort wird ein Versuch (Quelle probe), dann die Auswertung.
  function probeAbgeben() {
    if (!runde || !runde.probe || runde.probe.abgegeben) return;
    const fa = fach();
    for (const id of runde.liste) {
      const e = fa.ix.fragen.get(id);
      const wahl = runde.auswahl[id] || [];
      if (e && wahl.length && !runde.versuch[id]) {
        runde.versuch[id] = K.versuchBuchen(fa.fortschritt, id, { wahl }, jetzt(), geraet, 'probe').id;
      }
    }
    runde.probe.abgegeben = true;
    lokalSpeichern(fa.daten.fach);
    abgleichPlanen();
    zeige('runde-ende', {}, true);
  }

  // ---------- Einstellungen ----------
  function bildEinstellungen() {
    const teile = [kopf('Einstellungen')];
    const groesse = el('select', { class: 'eingabe', onchange: e => {
      einstellungen.rundeGroesse = Number(e.target.value);
      localStorage.setItem('altfragen_einstellungen', JSON.stringify(einstellungen));
    } }, ...[10, 20, 30, 50].map(n => el('option', { value: n, selected: n === einstellungen.rundeGroesse || null, text: `${n} Fragen` })));
    teile.push(el('label', { class: 'feld' }, el('span', { text: 'Wiederholung je Runde' }), groesse));
    teile.push(el('h3', { text: 'Drive' }));
    teile.push(el('p', { class: 'unter', text: D.gueltig() ? 'Verbunden. Der Zugang gilt eine Stunde und wird danach beim nächsten Tippen von selbst erneuert, Google blendet dafür kurz ein Fenster ein.' : 'Nicht verbunden.' }));
    teile.push(D.gueltig() ? knopf('Jetzt abgleichen', () => abgleich()) : verbindenKnopf('Verbinden', 'knopf'));
    for (const [id, fe] of Object.entries(sync.lesefehler)) {
      if (fe && fe.length) teile.push(el('p', { class: 'rot klein', text: `${faecher[id] ? faecher[id].daten.name : id}: im Lernskript nicht lesbar und übersprungen: ${fe.join(', ')}` }));
    }
    for (const fa of Object.values(faecher)) {
      teile.push(el('p', { class: 'unter klein', text: `${fa.daten.name}: Fragen vom ${new Date(fa.daten.stand).toLocaleDateString('de-DE')}, ${fa.ix.beantwortbar.length} beantwortbar` }));
    }
    teile.push(knopf('Lernstand als Datei sichern', sichern, 'leise'));
    if (D.gueltig()) teile.push(knopf('Abmelden', () => { D.abmelden(); zeige('einstellungen', {}, true); }, 'leise'));
    teile.push(el('p', { class: 'unter klein', text: `Version ${VERSION} · Gerät ${geraet}` }));
    teile.push(statusZeile());
    return teile;
  }
  function sichern() {
    const daten = Object.fromEntries(Object.entries(faecher).map(([id, fa]) => [id, fa.fortschritt]));
    const blob = new Blob([JSON.stringify(daten, null, 1)], { type: 'application/json' });
    const a = el('a', { href: URL.createObjectURL(blob), download: `altfragen-lernstand-${heute()}.json` });
    document.body.append(a);
    a.click();
    a.remove();
  }

  const BILDER = {
    start: bildStart, themen: bildThemen, thema: bildThema, frage: bildFrage, 'runde-ende': bildRundeEnde,
    'probe-wahl': bildProbeWahl, einstellungen: bildEinstellungen,
  };

  // ---------- Start ----------
  laden().then(() => {
    stapel.push({ name: 'start', param: {} });
    history.replaceState({ n: 1 }, '');
    // Eine unterbrochene Probeklausur geht dort weiter, wo sie war; die Uhr läuft dabei weiter
    if (probeWiederherstellen()) zeige('frage');
    else zeichnen();
    // Google im Hintergrund laden; ist der Schlüssel dieses Tabs noch gültig, sofort abgleichen
    D.vorbereiten(KONFIG.clientId, BEREICH).then(() => { if (D.gueltig()) abgleich(); else statusZeichnen(); }).catch(() => statusZeichnen());
  });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
