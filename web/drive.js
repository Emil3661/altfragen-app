// Anmeldung mit Google und Zugriff auf Drive, nur für Dateien, die die Anwendung JARVIS angelegt hat (drive.file).
// Der Zugriffsschlüssel gilt eine Stunde und liegt nur im Speicher des Tabs (sessionStorage), nie dauerhaft.
// Erneuern braucht einen Tipp, weil Google dafür ein kurzes Fenster öffnet, das Browser nur nach einer Berührung erlauben.
const Drive = (() => {
  const API = 'https://www.googleapis.com/drive/v3';
  const UPLOAD = 'https://www.googleapis.com/upload/drive/v3';
  const MERKER = 'altfragen_zugang';
  let client = null;
  let zugang = null;
  let wartend = null;

  // Gespeicherten Schlüssel dieses Tabs übernehmen, falls er noch mindestens eine Minute gilt.
  try {
    const roh = sessionStorage.getItem(MERKER);
    if (roh) zugang = JSON.parse(roh);
  } catch (e) { zugang = null; }

  function gueltig() {
    return !!(zugang && zugang.ablauf - Date.now() > 60 * 1000);
  }

  // Google-Skript laden und den Token-Client anlegen. Ohne Netz bleibt die App benutzbar, nur ohne Abgleich.
  function vorbereiten(clientId, bereich) {
    if (client) return Promise.resolve();
    return new Promise((fertig, fehler) => {
      const start = () => {
        client = google.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: bereich,
          callback: antwort => {
            if (!wartend) return;
            const w = wartend;
            wartend = null;
            if (antwort.error || !antwort.access_token) { w.fehler(new Error(antwort.error || 'keine Anmeldung')); return; }
            zugang = { token: antwort.access_token, ablauf: Date.now() + Number(antwort.expires_in || 3600) * 1000 };
            try { sessionStorage.setItem(MERKER, JSON.stringify(zugang)); } catch (e) { /* ohne Speicher gilt der Schlüssel nur bis zum Neuladen */ }
            try { localStorage.setItem('altfragen_angemeldet', '1'); } catch (e) { /* nur Hinweis für die Startseite */ }
            w.fertig();
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

  // Muss aus einem Tipp heraus aufgerufen werden. prompt '' = Zustimmung nur beim ersten Mal.
  function anmelden() {
    if (!client) return Promise.reject(new Error('Google nicht geladen'));
    return new Promise((fertig, fehler) => {
      wartend = { fertig, fehler };
      client.requestAccessToken({ prompt: '' });
    });
  }

  function abmelden() {
    if (zugang && window.google) google.accounts.oauth2.revoke(zugang.token, () => {});
    zugang = null;
    try { sessionStorage.removeItem(MERKER); localStorage.removeItem('altfragen_angemeldet'); } catch (e) { /* nichts zu tun */ }
  }

  // Eine Anfrage an Drive. 401 = Schlüssel abgelaufen: verwerfen, damit die App neu fragt.
  async function anfrage(url, optionen = {}) {
    if (!gueltig()) { const e = new Error('nicht angemeldet'); e.code = 401; throw e; }
    const antwort = await fetch(url, { ...optionen, headers: { ...(optionen.headers || {}), Authorization: 'Bearer ' + zugang.token } });
    if (antwort.status === 401) {
      zugang = null;
      try { sessionStorage.removeItem(MERKER); } catch (e) { /* nichts zu tun */ }
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

  return { vorbereiten, anmelden, abmelden, gueltig, suchen, metadaten, lesen, schreiben };
})();
