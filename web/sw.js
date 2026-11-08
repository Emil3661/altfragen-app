// Hält die App offline verfügbar: erst das Netz, damit neue Fassungen ankommen, ohne Netz die gespeicherte.
// Nur die eigenen Dateien der Seite. Anfragen an Google und Drive laufen nie durch diesen Speicher,
// Fragen und Lernstand liegen in IndexedDB.
const ABLAGE = 'altfragen-app-1';
const SCHALE = ['./', 'index.html', 'stil.css', 'konfig.js', 'kern.js', 'markdown.js', 'drive.js', 'app.js', 'manifest.webmanifest', 'icon.png'];

self.addEventListener('install', ereignis => {
  ereignis.waitUntil(caches.open(ABLAGE).then(a => a.addAll(SCHALE)).then(() => self.skipWaiting()));
});

// Alte Fassungen des Speichers entfernen
self.addEventListener('activate', ereignis => {
  ereignis.waitUntil(caches.keys().then(namen => Promise.all(namen.filter(n => n !== ABLAGE).map(n => caches.delete(n)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', ereignis => {
  const url = new URL(ereignis.request.url);
  if (ereignis.request.method !== 'GET' || url.origin !== self.location.origin) return;
  ereignis.respondWith(
    fetch(ereignis.request)
      .then(antwort => {
        if (antwort.ok) {
          const kopie = antwort.clone();
          caches.open(ABLAGE).then(a => a.put(ereignis.request, kopie));
        }
        return antwort;
      })
      .catch(() => caches.match(ereignis.request).then(t => t || caches.match('index.html'))),
  );
});
