// Hält die App offline verfügbar: erst das Netz, damit neue Fassungen ankommen, ohne Netz die gespeicherte.
// Nur die eigenen Dateien der Seite. Anfragen an Google und Drive laufen nie durch diesen Speicher,
// Fragen und Lernstand liegen in IndexedDB.
const PRAEFIX = 'altfragen-app-';
const ABLAGE = PRAEFIX + '3';
const SCHALE = ['./', 'index.html', 'stil.css', 'konfig.js', 'kern.js', 'markdown.js', 'drive.js', 'app.js', 'manifest.webmanifest', 'icon.png'];
// So lange wartet der Start auf das Netz, dann nimmt er die gespeicherte Fassung
const WARTEN_MS = 3000;

self.addEventListener('install', ereignis => {
  ereignis.waitUntil(caches.open(ABLAGE).then(a => a.addAll(SCHALE.map(u => new Request(u, { cache: 'no-cache' })))).then(() => self.skipWaiting()));
});

// Nur alte Fassungen dieser App entfernen. Andere Seiten unter derselben Adresse (etwa der Erreger-Trainer)
// haben eigene Speicher, die bleiben unberührt
self.addEventListener('activate', ereignis => {
  ereignis.waitUntil(caches.keys()
    .then(namen => Promise.all(namen.filter(n => n.startsWith(PRAEFIX) && n !== ABLAGE).map(n => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', ereignis => {
  const url = new URL(ereignis.request.url);
  if (ereignis.request.method !== 'GET' || url.origin !== self.location.origin) return;
  ereignis.respondWith(netzOderAblage(ereignis.request));
});

// Netz mit Zeitgrenze, am Browser-Zwischenspeicher vorbei (no-cache = beim Server nachfragen).
// Kommt das Netz zu spät oder gar nicht, antwortet die gespeicherte Fassung
async function netzOderAblage(anfrage) {
  const ablage = await caches.open(ABLAGE);
  const netz = fetch(anfrage, { cache: 'no-cache' }).then(antwort => {
    if (antwort.ok) ablage.put(anfrage, antwort.clone());
    return antwort;
  });
  const gespeichert = await ablage.match(anfrage);
  if (!gespeichert) return netz.catch(() => ablage.match('index.html'));
  const spaet = new Promise(fertig => setTimeout(() => fertig(gespeichert), WARTEN_MS));
  return Promise.race([netz.catch(() => gespeichert), spaet]);
}
