// Lernlogik der Altfragen-App ohne Bildschirm und ohne Netz, deshalb einzeln testbar.
// Rein: Fragendaten (fragen-<fach>.json), Fortschritt, Text des Lernskripts. Raus: Zustände, Fälligkeiten,
// Plan und der abgeglichene Stand. Regeln und Formate: FORMAT.md im Repo.
const Kern = (() => {
  const LEER = '#u0f0';
  const LEER_Z = Object.freeze({ wahl: [], unsicher: false, falsch: false });
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
  // 'richtig', 'unsicher', 'falsch' oder null, wenn der Versuch nichts aussagt (leere Wahl).
  function ergebnis(q, v) {
    if (q.typ === 'fragment') return null;
    if (q.typ === 'offen' || !q.optionen.length) {
      if (v.falsch) return 'falsch';
      return v.unsicher ? 'unsicher' : 'richtig';
    }
    const wahl = new Set((v.wahl || []).map(normal));
    if (!wahl.size) return null;
    const soll = new Set(q.optionen.filter(o => o.richtig).map(o => normal(o.t)));
    const gleich = wahl.size === soll.size && [...wahl].every(x => soll.has(x));
    if (!gleich) return 'falsch';
    return v.unsicher ? 'unsicher' : 'richtig';
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

  // ---------- Wiederholung ----------
  // Leiter wie in FORMAT.md: falsch 2 Tage, unsicher 3 Tage, danach richtig 7 und 21 Tage, dann fertig.
  // Richtig vor dem Fälligkeitstag (sofort noch einmal geübt) rückt die Leiter nicht vor.
  // Fälligkeit höchstens zwei Tage vor der Klausur, aber nie vor dem Folgetag des Versuchs.
  const ABSTAND = { falsch: 2, unsicher: 3 };
  const LEITER = [7, 21];
  function wiederholung(q, versuche, heute, klausur) {
    const vs = gueltige(versuche).filter(v => ergebnis(q, v));
    if (!vs.length) return { status: 'neu', faellig: null, letztes: null };
    let leiter = false;
    let stufe = 0;
    let faellig = null;
    let e = null;
    for (const v of vs) {
      e = ergebnis(q, v);
      const tag = tagVon(v.zeit);
      if (e !== 'richtig') {
        leiter = true; stufe = 0; faellig = plusTage(tag, ABSTAND[e]);
      } else if (leiter && faellig && tag < faellig) {
        continue;
      } else if (leiter) {
        stufe += 1;
        if (stufe <= LEITER.length) faellig = plusTage(tag, LEITER[stufe - 1]);
        else { leiter = false; faellig = null; }
      } else {
        faellig = null;
      }
      if (faellig && klausur) {
        const grenze = plusTage(klausur, -2);
        if (faellig > grenze) faellig = grenze;
        const frueh = plusTage(tag, 1);
        if (faellig < frueh) faellig = frueh;
      }
    }
    const status = faellig === null ? 'sicher' : (heute >= faellig ? 'faellig' : 'wartet');
    return { status, faellig, letztes: e };
  }

  // ---------- Fortschritt ----------
  function leererFortschritt(fach) {
    return { format: 1, fach, versuche: {}, schritte: {}, md: { zeit: null, basis: {}, ueberschrieben: {} } };
  }
  // Fehlende Teile ergänzen und unbrauchbare Versuche (ohne ID, Zeit oder Wahl) verwerfen,
  // damit eine beschädigte Datei die App nicht lahmlegt.
  function brauchbar(v) {
    return !!v && typeof v.id === 'string' && !Number.isNaN(Date.parse(v.zeit)) && Array.isArray(v.wahl);
  }
  function vervollstaendigen(f, fach) {
    const leer = leererFortschritt(fach);
    const g = { ...leer, ...(f || {}) };
    g.versuche = Object.fromEntries(Object.entries(g.versuche || {})
      .map(([id, liste]) => [id, Array.isArray(liste) ? liste.filter(brauchbar) : []]));
    g.schritte = { ...(g.schritte || {}) };
    g.md = { ...leer.md, ...(g.md || {}) };
    return g;
  }
  function kopie(x) {
    return JSON.parse(JSON.stringify(x));
  }
  function spaeter(a, b) {
    return (Date.parse(a || 0) || 0) > (Date.parse(b || 0) || 0);
  }

  // Zwei Stände vereinigen: Versuche über ihre ID, bei gleicher ID gewinnt das spätere "geaendert".
  // Ein Grabstein bleibt immer erhalten, auch wenn die andere Fassung später geändert wurde.
  // Schritte je Feld, md-Block als Ganzes.
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
    aus.md = spaeter(b.md.zeit, a.md.zeit) ? b.md : a.md;
    return aus;
  }

  // ---------- Abgleich mit dem Lernskript ----------
  // Drei-Wege-Vergleich je Frage zwischen basis (letzter gemeinsamer Stand), .md und letztem Versuch.
  // Rein: Fortschritt (schon mit Drive zusammengeführt), md-Text, modifiedTime der .md, erschlossene Daten, jetzt.
  // Raus: neuer Fortschritt, neuer md-Text oder null, geänderte Fragen, Lesefehler, Abbruchgrund oder null.
  // Bei Abbruch und wenn das Hochladen scheitert, gilt der alte md-Block weiter (mdAlt).
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
      // Nur "unsicher" angehakt, aber noch keine Option: Docs ist mitten in einer Antwort, abwarten
      if (q.optionen.length && !m.wahl.length && (m.unsicher || m.falsch)) {
        if (basis[q.id]) neueBasis[q.id] = basis[q.id];
        continue;
      }
      const km = schluessel(m);
      const kb = basis[q.id] || LEER;
      if (km !== kb && km !== LEER && !(ueb[q.id] || []).includes(km)) {
        uebernehmen(f, q, m, mdZeit, jetzt);
      }
      const letzter = letzterVersuch(f, q.id);
      const s = letzter ? zustandAus(letzter) : LEER_Z;
      const ks = schluessel(s);
      if (ks !== km) {
        geaendert.push(q.id);
        soll[q.id] = s;
        neueUeb[q.id] = [km, ...(neueUeb[q.id] || []).filter(k => k !== km)].slice(0, 3);
        // Geleert ohne Grabstein heißt: Die App kennt die Antwort gar nicht. Zurückgenommene zählen nicht
        if (ks === LEER && !(f.versuche[q.id] || []).length) geleert.push(q);
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

  // Änderung aus Docs als Versuch übernehmen. Gleiche Wahl wie zuletzt: nur die Merkmale anpassen.
  // Die ID aus Frage, Zustand und Zahl der bisherigen Versuche ist auf jedem Gerät gleich,
  // so legen zwei Geräte denselben Haken nicht doppelt an, auch wenn sie die .md zu verschiedenen Zeiten lesen.
  function uebernehmen(f, q, m, mdZeit, jetzt) {
    const letzter = letzterVersuch(f, q.id);
    if (letzter && gleicheWahl(letzter.wahl, m.wahl)) {
      if (!!letzter.unsicher !== m.unsicher || !!letzter.falsch !== m.falsch) {
        letzter.unsicher = m.unsicher;
        letzter.falsch = m.falsch;
        letzter.geaendert = jetzt;
      }
      return;
    }
    const zeit = mdZeit || jetzt;
    const liste = f.versuche[q.id] || (f.versuche[q.id] = []);
    const id = `docs:${q.id}:${schluessel(m)}:${gueltige(liste).length}`;
    if (liste.some(v => v.id === id)) return;
    liste.push({ id, zeit, wahl: [...m.wahl], unsicher: m.unsicher, falsch: m.falsch, quelle: 'docs', geaendert: jetzt, geloescht: null });
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
  // Für Wiederholung und Probeklausur, damit keine gemerkte Position hilft. Fester Startwert aus dem Samen:
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

  // Stand eines Themas: Zahlen je Status und Ergebnis des letzten Versuchs, Schritte, nächste offene Frage.
  function themaStand(t, f, heute, klausur) {
    const st = { gesamt: 0, beantwortet: 0, richtig: 0, falsch: 0, unsicher: 0, faellig: 0, wartet: 0, naechste: null };
    for (const q of t.fragen) {
      if (q.typ === 'fragment') continue;
      st.gesamt += 1;
      const w = wiederholung(q, f.versuche[q.id], heute, klausur);
      if (w.status === 'neu') { if (!st.naechste) st.naechste = q; continue; }
      st.beantwortet += 1;
      st[w.letztes] += 1;
      if (w.status === 'faellig') st.faellig += 1;
      if (w.status === 'wartet') st.wartet += 1;
    }
    st.meditricks = schrittWert(f, t.rang, 'meditricks');
    st.kern = schrittWert(f, t.rang, 'kern');
    st.fertig = st.beantwortet === st.gesamt && !!st.kern && !!st.meditricks;
    return st;
  }

  // Das Thema, an dem es weitergeht: das erste im Plan, das nicht fertig ist; optionale erst danach.
  function naechstesThema(daten, f, heute) {
    for (const nurPflicht of [true, false]) {
      for (const p of planListe(daten)) {
        if (nurPflicht && p.optional) continue;
        const st = themaStand(p.thema, f, heute, daten.klausur);
        if (!st.fertig) return { ...p, stand: st };
      }
    }
    return null;
  }

  // Tempo für den ersten Durchgang: offene Pflichtfragen bis sieben Tage vor der Klausur.
  function tempo(daten, f, heute) {
    const ziel = plusTage(daten.klausur, -7);
    const tage = Math.max(1, tageZwischen(heute, ziel) + 1);
    let offen = 0;
    for (const p of planListe(daten)) {
      if (p.optional) continue;
      for (const q of p.thema.fragen) {
        if (q.typ !== 'fragment' && !gueltige(f.versuche[q.id]).some(v => ergebnis(q, v))) offen += 1;
      }
    }
    return { ziel, tage, offen, proTag: Math.ceil(offen / tage), bisKlausur: tageZwischen(heute, daten.klausur) };
  }

  // Fällige Fragen über alle Themen, die am längsten fälligen zuerst, dann in Plan-Reihenfolge.
  function faellige(daten, f, heute) {
    const aus = [];
    planListe(daten).forEach((p, pos) => {
      for (const q of p.thema.fragen) {
        if (q.typ === 'fragment') continue;
        const w = wiederholung(q, f.versuche[q.id], heute, daten.klausur);
        if (w.status === 'faellig') aus.push({ frage: q, thema: p.thema, faellig: w.faellig, pos });
      }
    });
    return aus.sort((a, b) => (a.faellig < b.faellig ? -1 : a.faellig > b.faellig ? 1 : a.pos - b.pos));
  }

  // Nächster Termin, an dem wieder etwas fällig wird (für die Startseite).
  function naechsteFaelligkeit(daten, f, heute) {
    let min = null;
    for (const t of daten.themen) for (const q of t.fragen) {
      if (q.typ === 'fragment') continue;
      const w = wiederholung(q, f.versuche[q.id], heute, daten.klausur);
      if (w.status === 'wartet' && (!min || w.faellig < min)) min = w.faellig;
    }
    return min;
  }

  return {
    LEER, normal, schluessel, zustandAus, erschliessen, lernskriptLesen, lernskriptSchreiben, ergebnis,
    tagVon, plusTage, tageZwischen, gueltige, letzterVersuch, wiederholung, leererFortschritt, vervollstaendigen,
    zusammenfuehren, abgleichen, versuchBuchen, versuchAendern, versuchZuruecknehmen, schrittSetzen, schrittWert,
    planListe, themaStand, naechstesThema, tempo, faellige, naechsteFaelligkeit, mischen,
  };
})();
if (typeof module !== 'undefined') module.exports = Kern;
