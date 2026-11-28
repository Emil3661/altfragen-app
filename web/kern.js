// Lernlogik der Altfragen-App ohne Bildschirm und ohne Netz, deshalb einzeln testbar.
// Rein: Fragendaten (fragen-<fach>.json), Fortschritt, Text des Lernskripts. Raus: Zustände, Sammlungen,
// Plan und der abgeglichene Stand. Regeln und Formate: FORMAT.md im Repo.
const Kern = (() => {
  const LEER = '#u0f0';
  const SCHUTZ_GELEERT = 5;

  // ---------- Text vergleichbar machen ----------
  // Google Docs setzt beim Speichern Backslashes vor Satzzeichen und hängt Leerzeichen an.
  // normal() macht Docs-Fassung und Original vergleichbar, ohne Groß- und Kleinschreibung zu ändern.
  function normal(text) {
    let s = String(text == null ? '' : text)
      .replace(/\\([!-/:-@[-`{-~])/g, '$1')
      .replace(/ /g, ' ')
      .trim();
    // Umschließende Sternchen und Unterstriche (Kursiv- und Fettdruck) wiederholt entfernen
    let vorher;
    do {
      vorher = s;
      s = s.replace(/^([*_]+)(.*?)\1$/s, '$2').trim();
    } while (s !== vorher);
    return s.replace(/\s+/g, ' ');
  }

  // Schlüssel eines Zustands: gewählte Optionen sortiert, dann die beiden Merkmale. LEER = nichts angehakt.
  function schluessel(z) {
    const wahl = (z.wahl || []).map(normal).sort();
    return wahl.join('|') + '#u' + (z.unsicher ? 1 : 0) + 'f' + (z.falsch ? 1 : 0);
  }

  function zustandAus(v) {
    return { wahl: [...(v.wahl || [])], unsicher: !!v.unsicher, falsch: !!v.falsch };
  }

  // Schlüssel wieder zerlegen: Teil der Optionen, Merkmal unsicher, Merkmal falsch.
  // Die letzten fünf Zeichen haben immer die Form "#u0f0", davor stehen die Optionen.
  function teile(k) {
    return { wahl: k.slice(0, -5), unsicher: k.slice(-3, -2) === '1', falsch: k.slice(-1) === '1' };
  }

  // ---------- Fragendaten erschließen ----------
  // Einmal je Fach: Nachschlagen nach Frage-ID und nach (Thema, Nummer im Lernskript).
  function erschliessen(daten) {
    const fragen = new Map();
    const nachRangNr = new Map();
    const themen = new Map();
    const beantwortbar = [];
    for (const t of daten.themen) {
      themen.set(t.rang, t);
      for (const q of t.fragen) {
        fragen.set(q.id, { frage: q, thema: t });
        nachRangNr.set(t.rang + '#' + q.nr, q);
        if (q.typ !== 'fragment') beantwortbar.push(q);
      }
    }
    return { daten, fragen, nachRangNr, themen, beantwortbar };
  }

  // ---------- Lernskript lesen ----------
  // Zerlegt die .md zeilenweise: Themenkopf "## N · …", Fragekopf "**Frage N**", darunter Kästchen.
  // Rein: Text, erschlossene Daten. Raus: Zustand je Frage, Zeilen der Kästchen (zum Umschreiben),
  // Fehler (Frage unbekannt "<rang>#<nr>", Option unbekannt = Frage-ID) und die unlesbaren Fragen.
  const KASTEN = /^(\s*[-*+] \[)([ xX])(\] )(.*?)\s*$/;
  function lernskriptLesen(text, ix) {
    const zeilen = String(text).split('\n');
    const zustaende = {};
    const orte = {};
    const fehler = [];
    const kaputt = new Set();
    let rang = null;
    let akt = null;
    for (let i = 0; i < zeilen.length; i++) {
      const z = zeilen[i].endsWith('\r') ? zeilen[i].slice(0, -1) : zeilen[i];
      let m = /^## (\d+) · /.exec(z);
      if (m) { rang = Number(m[1]); akt = null; continue; }
      if (/^#{1,2} /.test(z)) { akt = null; continue; }
      m = /^\*\*Frage (\d+)\*\*/.exec(z);
      if (m) {
        akt = null;
        if (rang === null) continue;
        const q = ix.nachRangNr.get(rang + '#' + Number(m[1]));
        if (!q) { fehler.push(rang + '#' + Number(m[1])); continue; }
        if (q.typ === 'fragment') continue;
        akt = { q, z: { wahl: [], unsicher: false, falsch: false } };
        zustaende[q.id] = akt.z;
        orte[q.id] = [];
        continue;
      }
      if (!akt) continue;
      m = KASTEN.exec(z);
      if (!m) continue;
      const an = m[2] !== ' ';
      const inhalt = normal(m[4]);
      const rolle = merkmal(m[4]);
      if (rolle) {
        if (an) akt.z[rolle] = true;
        orte[akt.q.id].push({ zeile: i, rolle });
        continue;
      }
      const opt = akt.q.optionen.find(o => normal(o.t) === inhalt);
      if (!opt) {
        if (!kaputt.has(akt.q.id)) fehler.push(akt.q.id);
        kaputt.add(akt.q.id);
        continue;
      }
      if (an) akt.z.wahl.push(opt.t);
      orte[akt.q.id].push({ zeile: i, rolle: 'option', t: opt.t });
    }
    for (const id of kaputt) { delete zustaende[id]; delete orte[id]; }
    return { zustaende, orte, fehler, kaputt };
  }

  // Merkmal-Kästchen: Text ist "unsicher" oder "falsch", auch wenn Google Docs die nächste Zeile angehängt hat
  // ("*unsicher* **Hinweis:** …"). Raus: 'unsicher', 'falsch' oder null.
  function merkmal(roh) {
    const n = normal(roh);
    if (n === 'unsicher' || n === 'falsch') return n;
    const m = /^([*_]+)(unsicher|falsch)\1(\s|$)/.exec(String(roh).trim());
    return m ? m[2] : null;
  }

  // ---------- Lernskript umschreiben ----------
  // Setzt nur das Zeichen zwischen den eckigen Klammern; alle anderen Zeichen und Zeilenenden bleiben.
  function lernskriptSchreiben(text, orte, soll) {
    const zeilen = String(text).split('\n');
    for (const [id, z] of Object.entries(soll)) {
      const wahl = new Set(z.wahl.map(normal));
      for (const o of orte[id] || []) {
        const an = o.rolle === 'option' ? wahl.has(normal(o.t)) : !!z[o.rolle];
        zeilen[o.zeile] = zeilen[o.zeile].replace(/^(\s*[-*+] \[)[ xX](\] )/, '$1' + (an ? 'x' : ' ') + '$2');
      }
    }
    return zeilen.join('\n');
  }

  // ---------- Ergebnis eines Versuchs ----------
  // 'richtig', 'falsch' oder null, wenn der Versuch nichts aussagt (leere Wahl). Das Merkmal unsicher älterer
  // Versuche zählt hier nicht, es ist beim Laden zum Stern geworden.
  function ergebnis(q, v) {
    if (q.typ === 'fragment') return null;
    if (q.typ === 'offen' || !q.optionen.length) return v.falsch ? 'falsch' : 'richtig';
    const wahl = new Set((v.wahl || []).map(normal));
    if (!wahl.size) return null;
    const soll = new Set(q.optionen.filter(o => o.richtig).map(o => normal(o.t)));
    const gleich = wahl.size === soll.size && [...wahl].every(x => soll.has(x));
    return gleich ? 'richtig' : 'falsch';
  }

  // ---------- Kalendertage in Berliner Zeit ----------
  const TAG_FORMAT = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit' });
  function tagVon(zeit) {
    return TAG_FORMAT.format(new Date(zeit));
  }
  function plusTage(tag, n) {
    const d = new Date(tag + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function tageZwischen(von, bis) {
    return Math.round((Date.parse(bis + 'T12:00:00Z') - Date.parse(von + 'T12:00:00Z')) / 86400000);
  }

  // Nicht gelöschte Versuche nach Zeit; bei gleicher Zeit bleibt die Reihenfolge der Liste.
  function gueltige(versuche) {
    return (versuche || []).map((v, i) => [v, i]).filter(([v]) => !v.geloescht)
      .sort((a, b) => (Date.parse(a[0].zeit) - Date.parse(b[0].zeit)) || (a[1] - b[1])).map(([v]) => v);
  }
  function letzterVersuch(f, id) {
    const vs = gueltige(f.versuche[id]);
    return vs.length ? vs[vs.length - 1] : null;
  }

  // ---------- Stern ----------
  // Je Frage {wert: true|false, zeit}, unabhängig von den Versuchen. Ausschalten bleibt als wert false stehen,
  // damit das Zusammenführen einen Stern von einem anderen Gerät nicht zurückholt.
  function sternAn(f, id) {
    const s = f.sterne && f.sterne[id];
    return !!(s && s.wert);
  }
  function sternSetzen(f, id, wert, jetzt) {
    (f.sterne || (f.sterne = {}))[id] = { wert: !!wert, zeit: jetzt };
  }

  // Versuche mit Ergebnis nach Zeit, als [{v, e}]; zurückgenommene und solche ohne Aussage fallen weg
  function ergebnisse(q, versuche) {
    return gueltige(versuche).map(v => ({ v, e: ergebnis(q, v) })).filter(x => x.e);
  }
  // Beantwortet = mindestens ein Versuch mit Ergebnis (für Plan, Tempo, „Weiter mit Frage“)
  function beantwortet(q, versuche) {
    return ergebnisse(q, versuche).length > 0;
  }
  // Wie oft eine Frage falsch beantwortet wurde, zurückgenommene Versuche ausgenommen
  function falschZahl(q, versuche) {
    return gueltige(versuche).filter(v => ergebnis(q, v) === 'falsch').length;
  }

  // ---------- Fortschritt ----------
  function leererFortschritt(fach) {
    return { format: 1, fach, versuche: {}, schritte: {}, sterne: {}, md: { zeit: null, basis: {}, ueberschrieben: {} } };
  }
  // Fehlende Teile ergänzen und unbrauchbare Versuche (ohne ID, Zeit oder Wahl) und Sterne (ohne wahr/falsch
  // oder Zeit) verwerfen, damit eine beschädigte Datei die App nicht lahmlegt.
  function brauchbar(v) {
    return !!v && typeof v.id === 'string' && !Number.isNaN(Date.parse(v.zeit)) && Array.isArray(v.wahl);
  }
  function sternBrauchbar(s) {
    return !!s && typeof s.wert === 'boolean' && !Number.isNaN(Date.parse(s.zeit));
  }
  // Übernahme des alten Merkmals: Eine Frage ohne eigenen Stern-Eintrag, die einen nicht zurückgenommenen Versuch
  // mit unsicher hat, bekommt einen Stern {wert: true, zeit, alt: true}. Er wird jedes Mal neu aus den Versuchen
  // abgeleitet, damit ein veralteter Stand ihn nach dem Zusammenführen nicht festhält. Ein Umschalten in der App
  // oder in Docs schreibt einen eigenen Eintrag ohne alt, der von da an gilt.
  // Schlüssel sortiert, damit derselbe Stand immer denselben Text ergibt
  function sterneAbleiten(g) {
    const neu = {};
    for (const id of [...new Set([...Object.keys(g.sterne), ...Object.keys(g.versuche)])].sort()) {
      const s = g.sterne[id];
      if (s && !s.alt) { neu[id] = s; continue; }
      const alt = gueltige(g.versuche[id]).filter(v => v.unsicher);
      if (alt.length) neu[id] = { wert: true, zeit: alt[alt.length - 1].zeit, alt: true };
    }
    g.sterne = neu;
    return g;
  }
  function vervollstaendigen(f, fach) {
    const leer = leererFortschritt(fach);
    const g = { ...leer, ...(f || {}) };
    g.versuche = Object.fromEntries(Object.entries(g.versuche || {})
      .map(([id, liste]) => [id, Array.isArray(liste) ? liste.filter(brauchbar) : []]));
    g.schritte = { ...(g.schritte || {}) };
    g.sterne = Object.fromEntries(Object.entries(g.sterne && typeof g.sterne === 'object' ? g.sterne : {})
      .filter(([, s]) => sternBrauchbar(s)));
    g.md = { ...leer.md, ...(g.md || {}) };
    return sterneAbleiten(g);
  }
  function kopie(x) {
    return JSON.parse(JSON.stringify(x));
  }
  function spaeter(a, b) {
    return (Date.parse(a || 0) || 0) > (Date.parse(b || 0) || 0);
  }

  // Zwei Stände vereinigen: Versuche über ihre ID, bei gleicher ID gewinnt das spätere "geaendert".
  // Ein Grabstein bleibt immer erhalten, auch wenn die andere Fassung später geändert wurde.
  // Schritte je Feld, md-Block als Ganzes. Sterne: eigene Einträge je Frage nach "zeit" (bei gleicher Zeit gewinnt
  // der gesetzte), übernommene danach neu aus den vereinigten Versuchen.
  function zusammenfuehren(a, b) {
    const fach = (a && a.fach) || (b && b.fach);
    a = vervollstaendigen(kopie(a || {}), fach);
    b = vervollstaendigen(kopie(b || {}), fach);
    const aus = leererFortschritt(fach);
    for (const id of new Set([...Object.keys(a.versuche), ...Object.keys(b.versuche)])) {
      const nachId = new Map();
      for (const v of [...(a.versuche[id] || []), ...(b.versuche[id] || [])]) {
        const da = nachId.get(v.id);
        if (!da) { nachId.set(v.id, v); continue; }
        let sieger = spaeter(v.geaendert, da.geaendert) ? v : da;
        const tod = da.geloescht || v.geloescht;
        if (tod && !sieger.geloescht) sieger = { ...sieger, geloescht: tod };
        nachId.set(v.id, sieger);
      }
      aus.versuche[id] = [...nachId.values()].sort((x, y) => Date.parse(x.zeit) - Date.parse(y.zeit));
    }
    for (const rang of new Set([...Object.keys(a.schritte), ...Object.keys(b.schritte)])) {
      const sa = a.schritte[rang] || {};
      const sb = b.schritte[rang] || {};
      aus.schritte[rang] = {};
      for (const feld of new Set([...Object.keys(sa), ...Object.keys(sb)])) {
        const x = sa[feld];
        const y = sb[feld];
        aus.schritte[rang][feld] = !x ? y : !y ? x : (spaeter(y.zeit, x.zeit) ? y : x);
      }
    }
    for (const id of new Set([...Object.keys(a.sterne), ...Object.keys(b.sterne)])) {
      const x = a.sterne[id] && !a.sterne[id].alt ? a.sterne[id] : null;
      const y = b.sterne[id] && !b.sterne[id].alt ? b.sterne[id] : null;
      const s = !x ? y : !y ? x : spaeter(y.zeit, x.zeit) ? y : spaeter(x.zeit, y.zeit) ? x : (x.wert ? x : y);
      if (s) aus.sterne[id] = s;
    }
    aus.md = spaeter(b.md.zeit, a.md.zeit) ? b.md : a.md;
    return sterneAbleiten(aus);
  }

  // ---------- Abgleich mit dem Lernskript ----------
  // Drei-Wege-Vergleich je Frage zwischen basis (letzter gemeinsamer Stand), .md und App.
  // In der .md steht die App als Zustand: Optionen und falsch aus dem letzten Versuch, unsicher = Stern.
  // Rein: Fortschritt (schon mit Drive zusammengeführt), md-Text, modifiedTime der .md, erschlossene Daten, jetzt.
  // Raus: neuer Fortschritt, neuer md-Text oder null, geänderte Fragen, Lesefehler, Abbruchgrund oder null.
  // Bei Abbruch und wenn das Hochladen scheitert, gilt der alte md-Block weiter (mdAlt).
  function sollZustand(f, id) {
    const letzter = letzterVersuch(f, id);
    return { wahl: letzter ? [...(letzter.wahl || [])] : [], unsicher: sternAn(f, id), falsch: !!(letzter && letzter.falsch) };
  }
  function abgleichen(fortschritt, mdText, mdZeit, ix, jetzt) {
    const f = vervollstaendigen(kopie(fortschritt), ix.daten.fach);
    const mdAlt = kopie(f.md);
    const { zustaende, orte, fehler, kaputt } = lernskriptLesen(mdText, ix);
    const basis = f.md.basis || {};
    const ueb = f.md.ueberschrieben || {};
    const neueBasis = {};
    const neueUeb = kopie(ueb);
    const soll = {};
    const geaendert = [];
    const geleert = [];
    for (const q of ix.beantwortbar) {
      // Unlesbar oder nicht im Lernskript: nichts übernehmen, nichts schreiben, basis bleibt
      if (kaputt.has(q.id) || !zustaende[q.id]) {
        if (basis[q.id]) neueBasis[q.id] = basis[q.id];
        continue;
      }
      const m = zustaende[q.id];
      const km = schluessel(m);
      const kb = basis[q.id] || LEER;
      // Merkmal angehakt, aber keine Option, obwohl im letzten gemeinsamen Stand eine angehakt war: Docs ist
      // mitten in einer Antwort, abwarten. Sonst ist ein angehaktes unsicher allein der Stern
      if (q.optionen.length && !m.wahl.length && (m.falsch || (m.unsicher && teile(kb).wahl !== ''))) {
        if (basis[q.id]) neueBasis[q.id] = basis[q.id];
        continue;
      }
      if (km !== kb && km !== LEER && !(ueb[q.id] || []).includes(km)) {
        uebernehmen(f, q, m, kb, mdZeit, jetzt);
      }
      const s = sollZustand(f, q.id);
      const ks = schluessel(s);
      if (ks !== km) {
        geaendert.push(q.id);
        soll[q.id] = s;
        neueUeb[q.id] = [km, ...(neueUeb[q.id] || []).filter(k => k !== km)].slice(0, 3);
        // Haken entfernt, die die App gar nicht kennt: kein Versuch, auch kein zurückgenommener, und dabei geht eine
        // Antwort aus der .md verloren oder die Frage wird ganz geleert, ohne dass es einen Stern-Eintrag gibt
        const inMd = teile(km);
        const unbekannt = !(f.versuche[q.id] || []).length;
        if (unbekannt && (inMd.wahl !== '' || inMd.falsch || (ks === LEER && !f.sterne[q.id]))) geleert.push(q);
      }
      if (ks !== LEER) neueBasis[q.id] = ks;
    }
    if (geleert.length > SCHUTZ_GELEERT) {
      f.md = mdAlt;
      const liste = geleert.slice(0, 8).map(q => `${ix.fragen.get(q.id).thema.rang}.${q.nr}`).join(', ');
      return { fortschritt: f, mdNeu: null, geaendert: [], fehler, abbruch: `Abgleich angehalten: ${geleert.length} Fragen würden in der .md geleert (${liste}${geleert.length > 8 ? ' …' : ''})`, mdAlt };
    }
    f.md = { zeit: jetzt, basis: neueBasis, ueberschrieben: neueUeb };
    const neu = geaendert.length ? lernskriptSchreiben(mdText, orte, soll) : mdText;
    return { fortschritt: f, mdNeu: neu !== mdText ? neu : null, geaendert, fehler, abbruch: null, mdAlt };
  }

  // Änderung aus Docs übernehmen, getrennt nach Stern und Antwort, jeweils nur, was sich gegenüber basis
  // geändert hat. So löscht eine neue Antwort in Docs keinen Stern aus der App und umgekehrt.
  // Stern: Kästchen unsicher neu angehakt setzt ihn, Zeit = modifiedTime der .md; ist der Eintrag in der App
  // jünger, bleibt er. Abgehakt wird ignoriert wie jeder entfernte Haken: Eine veraltete Docs-Fassung soll keinen
  // Stern still löschen, entfernt wird er nur in der App.
  // Antwort: gleiche Wahl wie zuletzt passt nur falsch an, sonst neuer Versuch. Dessen ID aus Frage, Antwort und
  // Zahl der bisherigen Versuche ist auf jedem Gerät gleich, so legen zwei Geräte denselben Haken nicht doppelt an,
  // auch wenn sie die .md zu verschiedenen Zeiten lesen.
  function uebernehmen(f, q, m, kb, mdZeit, jetzt) {
    const b = teile(kb);
    const zeit = mdZeit || jetzt;
    if (m.unsicher && !b.unsicher) {
      const s = f.sterne[q.id];
      if (!s || (!s.wert && !spaeter(s.zeit, zeit))) f.sterne[q.id] = { wert: true, zeit };
    }
    const antwort = { wahl: [...m.wahl], unsicher: false, falsch: m.falsch };
    if (teile(schluessel(antwort)).wahl === b.wahl && m.falsch === b.falsch) return;
    // Frage mit Optionen ohne angehakte Option, offene Frage ohne falsch: Docs sagt nichts über eine Antwort
    if (q.optionen.length ? !m.wahl.length : !m.falsch && !letzterVersuch(f, q.id)) return;
    const letzter = letzterVersuch(f, q.id);
    if (letzter && gleicheWahl(letzter.wahl, m.wahl)) {
      if (!!letzter.falsch !== m.falsch) {
        letzter.falsch = m.falsch;
        letzter.geaendert = jetzt;
      }
      return;
    }
    const liste = f.versuche[q.id] || (f.versuche[q.id] = []);
    const id = `docs:${q.id}:${schluessel(antwort)}:${gueltige(liste).length}`;
    if (liste.some(v => v.id === id)) return;
    liste.push({ id, zeit, ...antwort, quelle: 'docs', geaendert: jetzt, geloescht: null });
  }

  function gleicheWahl(a, b) {
    const x = (a || []).map(normal).sort();
    const y = (b || []).map(normal).sort();
    return x.length === y.length && x.every((v, i) => v === y[i]);
  }

  // ---------- Versuche anlegen und zurücknehmen ----------
  function versuchBuchen(f, id, antwort, jetzt, geraet, quelle = 'app') {
    const v = {
      id: `${geraet}:${jetzt}:${Math.random().toString(36).slice(2, 8)}`,
      zeit: jetzt, wahl: [...(antwort.wahl || [])], unsicher: !!antwort.unsicher, falsch: !!antwort.falsch,
      quelle, geaendert: jetzt, geloescht: null,
    };
    (f.versuche[id] || (f.versuche[id] = [])).push(v);
    return v;
  }
  function versuchAendern(f, id, versuchId, aenderung, jetzt) {
    const v = (f.versuche[id] || []).find(x => x.id === versuchId);
    if (!v) return null;
    Object.assign(v, aenderung, { geaendert: jetzt });
    return v;
  }
  function versuchZuruecknehmen(f, id, versuchId, jetzt) {
    return versuchAendern(f, id, versuchId, { geloescht: jetzt }, jetzt);
  }

  // Ein Schritt im Plan (Meditricks, Kern) mit Zeitstempel, damit zwei Geräte ihn zusammenführen können.
  function schrittSetzen(f, rang, feld, wert, jetzt) {
    const s = f.schritte[rang] || (f.schritte[rang] = {});
    s[feld] = { wert, zeit: jetzt };
  }
  function schrittWert(f, rang, feld) {
    const s = f.schritte[rang] && f.schritte[rang][feld];
    return s ? s.wert : null;
  }

  // ---------- Optionen neu mischen ----------
  // Für Sammlungen und Probeklausur, damit keine gemerkte Position hilft. Fester Startwert aus dem Samen:
  // dieselbe Runde zeigt dieselbe Reihenfolge. Sammeloptionen (fest) bleiben am Ende.
  function mischen(optionen, samen) {
    let h = 2166136261;
    for (const c of String(samen)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; }
    const zufall = () => {
      h = (h + 0x6d2b79f5) >>> 0;
      let t = h;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const frei = optionen.filter(o => !o.fest);
    for (let i = frei.length - 1; i > 0; i--) {
      const j = Math.floor(zufall() * (i + 1));
      [frei[i], frei[j]] = [frei[j], frei[i]];
    }
    return [...frei, ...optionen.filter(o => o.fest)];
  }

  // ---------- Plan ----------
  // Reihenfolge der Themen: nach Rang, oder Blöcke mit Stufe A, dann B, und alle C-Themen am Ende als optional.
  function planListe(daten) {
    const themen = [...daten.themen];
    if (daten.plan !== 'block-stufe') {
      return themen.sort((a, b) => a.rang - b.rang).map(t => ({ thema: t, optional: false }));
    }
    const bloecke = daten.bloecke.map(b => b.nr);
    const nachBlock = nr => themen.filter(t => t.block === nr).sort((a, b) => a.rang - b.rang);
    const liste = [];
    for (const nr of bloecke) {
      const im = nachBlock(nr);
      for (const t of im.filter(t => t.stufe === 'A')) liste.push({ thema: t, optional: false });
      for (const t of im.filter(t => t.stufe !== 'A' && t.stufe !== 'C')) liste.push({ thema: t, optional: false });
    }
    for (const nr of bloecke) for (const t of nachBlock(nr).filter(t => t.stufe === 'C')) liste.push({ thema: t, optional: true });
    const drin = new Set(liste.map(x => x.thema.rang));
    for (const t of themen.filter(t => !drin.has(t.rang))) liste.push({ thema: t, optional: false });
    return liste;
  }

  // Stand eines Themas: beantwortete Fragen, Ergebnis der letzten Antwort je Frage, Schritte, nächste offene Frage.
  function themaStand(t, f) {
    const st = { gesamt: 0, beantwortet: 0, richtig: 0, falsch: 0, naechste: null };
    for (const q of t.fragen) {
      if (q.typ === 'fragment') continue;
      st.gesamt += 1;
      const vs = ergebnisse(q, f.versuche[q.id]);
      if (!vs.length) { if (!st.naechste) st.naechste = q; continue; }
      st.beantwortet += 1;
      st[vs[vs.length - 1].e] += 1;
    }
    st.meditricks = schrittWert(f, t.rang, 'meditricks');
    st.kern = schrittWert(f, t.rang, 'kern');
    // Fertig, sobald jede Frage einmal beantwortet ist. Meditricks und Kern zeigt die App als Schritte an,
    // sie halten den Plan aber nicht auf
    st.fertig = st.beantwortet === st.gesamt;
    return st;
  }

  // Das Thema, an dem es weitergeht: das erste im Plan, das nicht fertig ist; optionale erst danach.
  function naechstesThema(daten, f) {
    for (const nurPflicht of [true, false]) {
      for (const p of planListe(daten)) {
        if (nurPflicht && p.optional) continue;
        const st = themaStand(p.thema, f);
        if (!st.fertig) return { ...p, stand: st };
      }
    }
    return null;
  }

  // Tempo für den ersten Durchgang: offene Pflichtfragen bis zum Zieldatum des Fachs (durchgang),
  // ohne eigenes Ziel bis sieben Tage vor der Klausur. a || b = a, wenn a gesetzt ist, sonst b
  function tempo(daten, f, heute) {
    const ziel = daten.durchgang || plusTage(daten.klausur, -7);
    const tage = Math.max(1, tageZwischen(heute, ziel) + 1);
    let offen = 0;
    for (const p of planListe(daten)) {
      if (p.optional) continue;
      for (const q of p.thema.fragen) {
        if (q.typ !== 'fragment' && !beantwortet(q, f.versuche[q.id])) offen += 1;
      }
    }
    return { ziel, tage, offen, proTag: Math.ceil(offen / tage), bisKlausur: tageZwischen(heute, daten.klausur) };
  }

  // ---------- Sammlungen ----------
  // Je Frage: Zahl der falschen Versuche, ob der letzte falsch war, Zeit des letzten Versuchs (null = nie geübt)
  // und Position des Themas im Plan. Zurückgenommene Versuche zählen nicht.
  function sammelEintrag(q, t, f, pos) {
    const vs = ergebnisse(q, f.versuche[q.id]);
    const letzter = vs.length ? vs[vs.length - 1] : null;
    return { frage: q, thema: t, falsch: vs.filter(x => x.e === 'falsch').length, zuletztFalsch: !!letzter && letzter.e === 'falsch',
      zuletzt: letzter ? letzter.v.zeit : null, pos };
  }
  // Am längsten nicht geübte zuerst (nie geübte ganz vorn), bei Gleichstand nach Plan.
  // So decken mehrere kurze Runden nacheinander die ganze Sammlung ab
  function nachUebung(a, b) {
    const za = a.zuletzt ? Date.parse(a.zuletzt) : -Infinity;
    const zb = b.zuletzt ? Date.parse(b.zuletzt) : -Infinity;
    return (za < zb ? -1 : za > zb ? 1 : 0) || (a.pos - b.pos);
  }

  // Falsch: jede Frage, die je falsch beantwortet wurde, auch wenn sie inzwischen sitzt.
  // Zuerst die, deren letzte Antwort falsch war, darin und danach am längsten nicht geübte zuerst.
  // Raus: [{frage, thema, falsch: Anzahl, zuletztFalsch, zuletzt: ISO-Zeit des letzten Versuchs, pos}]
  function falschSammlung(daten, f) {
    const aus = [];
    planListe(daten).forEach((p, pos) => {
      for (const q of p.thema.fragen) {
        if (q.typ === 'fragment') continue;
        const x = sammelEintrag(q, p.thema, f, pos);
        if (x.falsch) aus.push(x);
      }
    });
    return aus.sort((a, b) => (b.zuletztFalsch - a.zuletztFalsch) || nachUebung(a, b));
  }

  // Markiert: genau die Fragen mit Stern, am längsten nicht geübte zuerst. Gleiche Felder wie falschSammlung.
  function markiertSammlung(daten, f) {
    const aus = [];
    planListe(daten).forEach((p, pos) => {
      for (const q of p.thema.fragen) if (sternAn(f, q.id)) aus.push(sammelEintrag(q, p.thema, f, pos));
    });
    return aus.sort(nachUebung);
  }

  // ---------- Themenranking ----------
  // Rein: Fragendaten, Fortschritt. Raus: eine Zeile je Thema nach Rang mit erwarteten Fragen, kumuliertem Anteil
  // und Trend aus "meta" sowie dem Haken (Schritt "ranking"). Fehlt "kumuliert" in meta, wird er aus den
  // erwarteten Fragen bis zu diesem Rang aufsummiert. Fehlende Angaben bleiben null.
  function rankingZeilen(daten, f) {
    const zahl = s => Number(s.replace(',', '.'));
    let summe = 0;
    return [...daten.themen].sort((a, b) => a.rang - b.rang).map(t => {
      const m = t.meta || '';
      const erw = /erwartet ([\d.,]+) von (\d+)/.exec(m);
      const kum = /kumuliert (\d+) %/.exec(m);
      const trend = /Trend (\S+)/.exec(m);
      const erwartet = erw ? zahl(erw[1]) : null;
      const von = erw ? Number(erw[2]) : null;
      if (erwartet !== null) summe += erwartet;
      return {
        rang: t.rang, titel: t.titel, stufe: t.stufe || null, erwartet, von,
        kumuliert: kum ? Number(kum[1]) : (von ? Math.round(100 * summe / von) : null),
        trend: trend ? trend[1] : null,
        abgehakt: schrittWert(f, t.rang, 'ranking') === 'ja',
      };
    });
  }

  // ---------- Fächerliste ----------
  // Semester einer Klausur aus dem Datum (JJJJ-MM-TT): Januar bis April gehört zum Wintersemester davor,
  // Mai bis September zum Sommersemester, Oktober bis Dezember zum Wintersemester, das dann beginnt.
  function semesterVon(tag) {
    const zwei = n => String((n + 100) % 100).padStart(2, '0');
    const j = Number(tag.slice(2, 4));
    const mo = Number(tag.slice(5, 7));
    if (mo <= 4) return `WiSe ${zwei(j - 1)}/${zwei(j)}`;
    if (mo <= 9) return `SoSe ${zwei(j)}`;
    return `WiSe ${zwei(j)}/${zwei(j + 1)}`;
  }
  // Rein: [{name, klausur, …}], heute. Raus: [{titel, faecher}], kommende Klausuren nach Datum und je Semester
  // gruppiert, vergangene zuletzt unter „Vorbei“, die jüngste zuerst. localeCompare vergleicht Texte nach Alphabet.
  function faecherGruppen(liste, heute) {
    const tag = x => String(x.klausur || '');
    const kommend = liste.filter(x => tag(x) >= heute).sort((a, b) => tag(a).localeCompare(tag(b)) || a.name.localeCompare(b.name, 'de'));
    const vorbei = liste.filter(x => tag(x) < heute).sort((a, b) => tag(b).localeCompare(tag(a)));
    const gruppen = [];
    for (const x of kommend) {
      const s = semesterVon(tag(x));
      if (!gruppen.length || gruppen[gruppen.length - 1].titel !== s) gruppen.push({ titel: s, faecher: [] });
      gruppen[gruppen.length - 1].faecher.push(x);
    }
    if (vorbei.length) gruppen.push({ titel: 'Vorbei', faecher: vorbei });
    return gruppen;
  }

  return {
    LEER, normal, schluessel, zustandAus, erschliessen, lernskriptLesen, lernskriptSchreiben, ergebnis, ergebnisse,
    beantwortet, falschZahl, tagVon, plusTage, tageZwischen, gueltige, letzterVersuch, leererFortschritt,
    vervollstaendigen, zusammenfuehren, abgleichen, sollZustand, versuchBuchen, versuchAendern, versuchZuruecknehmen,
    schrittSetzen, schrittWert, sternAn, sternSetzen, planListe, themaStand, naechstesThema, tempo, mischen,
    falschSammlung, markiertSammlung, rankingZeilen, semesterVon, faecherGruppen,
  };
})();
if (typeof module !== 'undefined') module.exports = Kern;
