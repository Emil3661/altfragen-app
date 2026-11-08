// Kleine Markdown-Teilmenge für Kern, Lösungen und Tabellen: Absätze, Listen (verschachtelt), Tabellen,
// Zwischentitel, fett und kursiv. Erzeugt Knoten über createElement und textContent, nie über innerHTML,
// damit kein Text aus den Daten als HTML ausgeführt werden kann.
const Markdown = (() => {
  // ---------- Zeile in Textstücke zerlegen ----------
  // Rein: eine Zeile. Raus: Liste aus {t:'text', s} | {t:'fett', k:[…]} | {t:'kursiv', k:[…]}.
  // Backslash vor einem Satzzeichen (Escape aus Google Docs) wird zum Zeichen selbst.
  function zeile(s) {
    const aus = [];
    let text = '';
    const flush = () => { if (text) { aus.push({ t: 'text', s: text }); text = ''; } };
    let i = 0;
    while (i < s.length) {
      const c = s[i];
      if (c === '\\' && i + 1 < s.length && /[!-/:-@[-`{-~]/.test(s[i + 1])) { text += s[i + 1]; i += 2; continue; }
      if (s.startsWith('**', i)) {
        const ende = s.indexOf('**', i + 2);
        if (ende > i + 2) { flush(); aus.push({ t: 'fett', k: zeile(s.slice(i + 2, ende)) }); i = ende + 2; continue; }
      }
      if ((c === '*' || c === '_') && s[i + 1] !== c && s[i + 1] !== ' ' && s[i + 1] !== undefined) {
        // Kursiv nur bei schließendem Gegenstück; "_" nur am Wortanfang, damit snake_case Text bleibt
        const ende = s.indexOf(c, i + 1);
        const wortanfang = c === '*' || i === 0 || /\W/.test(s[i - 1]);
        if (ende > i + 1 && s[ende - 1] !== ' ' && s[ende + 1] !== c && wortanfang) {
          flush(); aus.push({ t: 'kursiv', k: zeile(s.slice(i + 1, ende)) }); i = ende + 1; continue;
        }
      }
      text += c;
      i += 1;
    }
    flush();
    return aus;
  }

  // ---------- Text in Blöcke zerlegen ----------
  // Raus: Liste aus {t:'absatz', zeilen:[…]} | {t:'liste', geordnet, punkte:[{k, unter}]} | {t:'tabelle', kopf, zeilen}
  // | {t:'titel', k}. Listen-Einrückung: zwei Leerzeichen je Ebene.
  const PUNKT = /^(\s*)([-*+]|\d+[.)]) (.*)$/;
  function bloecke(text) {
    const zeilen = String(text || '').split(/\r?\n/);
    const aus = [];
    let absatz = null;
    let stapel = null;
    let i = 0;
    const schliessen = () => { absatz = null; stapel = null; };
    while (i < zeilen.length) {
      const z = zeilen[i].replace(/\s+$/, '');
      if (!z.trim()) { schliessen(); i += 1; continue; }
      if (/^\s*\|/.test(z)) {
        schliessen();
        const roh = [];
        while (i < zeilen.length && /^\s*\|/.test(zeilen[i])) { roh.push(zeilen[i].trim()); i += 1; }
        aus.push(tabelle(roh));
        continue;
      }
      const titel = /^#{1,6} (.*)$/.exec(z);
      if (titel) { schliessen(); aus.push({ t: 'titel', k: zeile(titel[1]) }); i += 1; continue; }
      const p = PUNKT.exec(z);
      if (p) {
        absatz = null;
        const ebene = Math.floor(p[1].length / 2);
        const geordnet = /\d/.test(p[2]);
        if (!stapel) {
          const wurzel = { t: 'liste', geordnet, punkte: [] };
          aus.push(wurzel);
          stapel = [wurzel];
        }
        // Tiefer eingerückt: Unterliste am letzten Punkt; flacher: zurück auf die passende Ebene
        while (stapel.length > ebene + 1) stapel.pop();
        let liste = stapel[stapel.length - 1];
        if (ebene + 1 > stapel.length && liste.punkte.length) {
          const letzter = liste.punkte[liste.punkte.length - 1];
          letzter.unter = letzter.unter || { t: 'liste', geordnet, punkte: [] };
          liste = letzter.unter;
          stapel.push(liste);
        }
        liste.punkte.push({ k: zeile(p[3]), unter: null });
        i += 1;
        continue;
      }
      stapel = null;
      if (!absatz) { absatz = { t: 'absatz', zeilen: [] }; aus.push(absatz); }
      absatz.zeilen.push(zeile(z.trim()));
      i += 1;
    }
    return aus;
  }

  // Tabelle: Trennzeile |---| fällt weg; die Zeile davor ist Kopf, außer sie ist leer.
  function tabelle(roh) {
    const zellen = r => r.replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(x => zeile(x.trim()));
    const trenn = r => /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(r);
    let kopf = null;
    const zeilen = [];
    roh.forEach((r, n) => {
      if (trenn(r)) return;
      if (n === 0 && roh[1] && trenn(roh[1])) {
        const k = zellen(r);
        if (k.some(c => c.length)) kopf = k;
        return;
      }
      zeilen.push(zellen(r));
    });
    return { t: 'tabelle', kopf, zeilen };
  }

  // ---------- Blöcke als Knoten ----------
  function zuDom(text, doc = document) {
    const frag = doc.createDocumentFragment();
    for (const b of bloecke(text)) frag.appendChild(block(b, doc));
    return frag;
  }
  function inline(teile, doc) {
    const frag = doc.createDocumentFragment();
    for (const x of teile) {
      if (x.t === 'text') frag.appendChild(doc.createTextNode(x.s));
      else {
        const n = doc.createElement(x.t === 'fett' ? 'strong' : 'em');
        n.appendChild(inline(x.k, doc));
        frag.appendChild(n);
      }
    }
    return frag;
  }
  function block(b, doc) {
    if (b.t === 'absatz') {
      const p = doc.createElement('p');
      b.zeilen.forEach((z, n) => { if (n) p.appendChild(doc.createElement('br')); p.appendChild(inline(z, doc)); });
      return p;
    }
    if (b.t === 'titel') {
      const h = doc.createElement('h4');
      h.appendChild(inline(b.k, doc));
      return h;
    }
    if (b.t === 'liste') {
      const l = doc.createElement(b.geordnet ? 'ol' : 'ul');
      for (const p of b.punkte) {
        const li = doc.createElement('li');
        li.appendChild(inline(p.k, doc));
        if (p.unter) li.appendChild(block(p.unter, doc));
        l.appendChild(li);
      }
      return l;
    }
    const huelle = doc.createElement('div');
    huelle.className = 'tabelle';
    const t = doc.createElement('table');
    if (b.kopf) {
      const tr = doc.createElement('tr');
      for (const c of b.kopf) { const th = doc.createElement('th'); th.appendChild(inline(c, doc)); tr.appendChild(th); }
      t.appendChild(tr);
    }
    for (const z of b.zeilen) {
      const tr = doc.createElement('tr');
      for (const c of z) { const td = doc.createElement('td'); td.appendChild(inline(c, doc)); tr.appendChild(td); }
      t.appendChild(tr);
    }
    huelle.appendChild(t);
    return huelle;
  }

  return { zeile, bloecke, zuDom, inline };
})();
if (typeof module !== 'undefined') module.exports = Markdown;
