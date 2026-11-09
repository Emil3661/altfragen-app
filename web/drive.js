// Anmeldung mit Google und Zugriff auf Drive, nur für Dateien, die die Anwendung JARVIS angelegt hat (drive.file).
// Der Zugriffsschlüssel gilt eine Stunde und liegt im Browser (localStorage), damit er ein Schließen und
// Wiederöffnen der App übersteht. Dazu wird das Konto gemerkt: Mit ihm als Hinweis öffnet Google beim Erneuern
// nur ein kurzes Fenster ohne Kontoauswahl, das sich selbst schließt. Browser erlauben das nur nach einer Berührung.
const Drive = (() => {
  const API = 'https://www.googleapis.com/drive/v3';
  const UPLOAD = 'https://www.googleapis.com/upload/drive/v3';
  const MERKER = 'altfragen_zugang';
  const KONTO = 'altfragen_konto';
  // So lange wartet eine Anmeldung auf Google, danach gilt sie als abgebrochen
  const ANMELDUNG_MAX_MS = 2 * 60 * 1000;
  let client = null;
  let zugang = null;
  let wartend = null;
  let laufend = null;
  let nachAnmeldung = null;
  // Zählt Abmeldungen hoch. Eine Rückmeldung von Google oder eine Kontoabfrage aus der Zeit davor wird verworfen
  let epoche = 0;
  let anfrageEpoche = 0;

  const konto = () => { try { return localStorage.getItem(KONTO) || ''; } catch (e) { return ''; } };
  function gespeichert() {
    try { return JSON.parse(localStorage.getItem(MERKER) || 'null'); } catch (e) { return null; }
  }
  function zugangMerken(z) {
    zugang = z;
    try {
      if (z) localStorage.setItem(MERKER, JSON.stringify(z)); else localStorage.removeItem(MERKER);
    } catch (e) { /* ohne Speicher gilt der Schlüssel nur bis zum Neuladen */ }
  }
  // Die Mailadresse des angemeldeten Kontos, als Hinweis für Google beim nächsten Erneuern
  async function kontoMerken() {
    const e = epoche;
    try {
      const a = await (await anfrage(`${API}/about?fields=user(emailAddress)`)).json();
      if (e === epoche && a.user && a.user.emailAddress) localStorage.setItem(KONTO, a.user.emailAddress);
    } catch (f) { /* ohne Konto fragt Google beim nächsten Mal nach dem Konto */ }
  }

  // Gilt der Schlüssel noch mindestens eine Minute? Wenn nicht, den gespeicherten lesen:
  // Ein anderer Tab der App kann ihn inzwischen erneuert haben
  function frisch(z) {
    return !!(z && z.token && z.ablauf - Date.now() > 60 * 1000);
  }
  function gueltig() {
    if (frisch(zugang)) return true;
    const g = gespeichert();
    if (frisch(g)) { zugang = g; return true; }
    return false;
  }

  // Google-Skript laden und den Token-Client anlegen. Ohne Netz bleibt die App benutzbar, nur ohne Abgleich.
  function vorbereiten(clientId, bereich) {
    if (client) return Promise.resolve();
    return new Promise((fertig, fehler) => {
      const start = () => {
        client = google.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: bereich,
          // Ein Schlüssel wird immer übernommen, auch wenn Google das Fenster vorher als geschlossen gemeldet hat
          // (im installierten Modus kann GIS den Fensterzustand nicht immer lesen). Ausnahme: inzwischen abgemeldet
          callback: antwort => {
            const w = wartend;
            wartend = null;
            if (anfrageEpoche !== epoche) return;
            if (antwort.error || !antwort.access_token) { if (w) w.fehler(new Error(antwort.error || 'keine Anmeldung')); return; }
            zugangMerken({ token: antwort.access_token, ablauf: Date.now() + Number(antwort.expires_in || 3600) * 1000 });
            if (!konto()) kontoMerken();
            if (w) w.fertig();
            else if (nachAnmeldung) nachAnmeldung();
          },
          error_callback: f => {
            if (!wartend) return;
            const w = wartend;
            wartend = null;
            w.fehler(new Error(f && f.type === 'popup_closed' ? 'Fenster geschlossen' : (f && f.type) || 'Anmeldung gescheitert'));
          },
        });
        fertig();
      };
      if (window.google && google.accounts && google.accounts.oauth2) { start(); return; }
      const s = document.createElement('script');
      s.src = 'https://accounts.google.com/gsi/client';
      s.async = true;
      s.onload = start;
      s.onerror = () => fehler(new Error('Google nicht erreichbar'));
      document.head.appendChild(s);
    });
  }

  // Muss aus einem Tipp heraus aufgerufen werden. prompt '' = Zustimmung nur beim ersten Mal,
  // login_hint = gemerktes Konto, dann ohne Kontoauswahl.
  // Läuft schon eine Anmeldung, warten weitere Aufrufer auf dieselbe. neu = true (Tipp auf „Verbinden“) verwirft
  // eine laufende und fragt neu, damit ein liegen gebliebenes Google-Fenster nie den Weg versperrt.
  // Meldet sich Google nicht, gilt die Anmeldung nach zwei Minuten als gescheitert.
  function anmelden(neu = false) {
    if (!client) return Promise.reject(new Error('Google nicht geladen'));
    if (laufend && !neu) return laufend;
    if (wartend) { wartend.fehler(new Error('Anmeldung neu gestartet')); wartend = null; }
    anfrageEpoche = epoche;
    const diese = new Promise((fertig, fehler) => {
      // w = diese eine Anfrage; die Uhr gibt nur sie frei, nicht eine spätere
      const w = {};
      const uhr = setTimeout(() => {
        if (wartend === w) wartend = null;
        fehler(new Error('Google hat nicht geantwortet'));
      }, ANMELDUNG_MAX_MS);
      w.fertig = () => { clearTimeout(uhr); fertig(); };
      w.fehler = f => { clearTimeout(uhr); fehler(f); };
      wartend = w;
      const k = konto();
      client.requestAccessToken(k ? { prompt: '', login_hint: k } : { prompt: '' });
    });
    laufend = diese;
    diese.catch(() => {}).finally(() => { if (laufend === diese) laufend = null; });
    return diese;
  }
  // Still erneuern geht nur, wenn Google geladen ist und auf diesem Gerät schon einmal ein Konto angemeldet war
  function kannStillErneuern() {
    return !!client && !laufend && !!konto();
  }

  function abmelden() {
    epoche += 1;
    if (wartend) { wartend.fehler(new Error('abgemeldet')); wartend = null; }
    if (zugang && window.google) google.accounts.oauth2.revoke(zugang.token, () => {});
    zugangMerken(null);
    try { localStorage.removeItem(KONTO); } catch (e) { /* nichts zu tun */ }
  }
  function beiAnmeldung(f) {
    nachAnmeldung = f;
  }

  // Eine Anfrage an Drive. 401 = Schlüssel abgelaufen: verwerfen, damit die App neu fragt.
  // Gespeichert gelöscht wird er nur, wenn dort noch derselbe steht, nicht ein neuerer aus einem anderen Tab.
  async function anfrage(url, optionen = {}) {
    if (!gueltig()) { const e = new Error('nicht angemeldet'); e.code = 401; throw e; }
    const benutzt = zugang.token;
    const antwort = await fetch(url, { ...optionen, headers: { ...(optionen.headers || {}), Authorization: 'Bearer ' + benutzt } });
    if (antwort.status === 401) {
      const g = gespeichert();
      if (!g || g.token === benutzt) zugangMerken(null);
      else if (zugang && zugang.token === benutzt) zugang = null;
    }
    if (!antwort.ok) {
      let text = '';
      try { text = (await antwort.json()).error.message; } catch (e) { text = antwort.statusText; }
      const e = new Error(`Drive ${antwort.status}: ${text}`);
      e.code = antwort.status;
      throw e;
    }
    return antwort;
  }

  // Dateien dieser Anwendung mit einer bestimmten Rolle (appProperties.altfragenApp) finden.
  async function suchen(rolle) {
    const q = `appProperties has { key='altfragenApp' and value='${rolle}' } and trashed = false`;
    const url = `${API}/files?spaces=drive&pageSize=50&fields=files(id,name,modifiedTime)&q=${encodeURIComponent(q)}`;
    return (await (await anfrage(url)).json()).files || [];
  }

  async function metadaten(id) {
    return (await anfrage(`${API}/files/${encodeURIComponent(id)}?fields=id,name,modifiedTime,md5Checksum,size`)).json();
  }

  async function lesen(id) {
    return (await anfrage(`${API}/files/${encodeURIComponent(id)}?alt=media`, { cache: 'no-store' })).text();
  }

  // Inhalt ersetzen, die Datei-ID bleibt. Raus: neue modifiedTime.
  async function schreiben(id, text, mime) {
    const url = `${UPLOAD}/files/${encodeURIComponent(id)}?uploadType=media&fields=id,modifiedTime`;
    return (await anfrage(url, { method: 'PATCH', headers: { 'Content-Type': mime + '; charset=UTF-8' }, body: text })).json();
  }

  return { vorbereiten, anmelden, kannStillErneuern, abmelden, beiAnmeldung, gueltig, suchen, metadaten, lesen, schreiben };
})();
