/* Çorlu BİLSEM Ders Programı — çevrimdışı önbellek.
   Strateji: önce önbellek (anında açılır, engelli ağda da çalışır),
   arka planda tazele (bir sonraki açılışta güncel sürüm gelir).
   MEB filtresi engel sayfasını HTTP 200 ile döndürebildiği için
   yalnız gerçekten bizim sayfamıza benzeyen yanıtlar önbelleğe yazılır. */
const AD = "bilsem-program-v2";
const DOSYALAR = ["./", "./index.html", "./manifest.webmanifest",
                  "./icon-180.png", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(AD).then(c => c.addAll(DOSYALAR)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== AD).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/* Filtre "engellendi" sayfasını HTTP 200 ile döndürebilir. Her dosya türü
   için yanıtın gerçekten beklenen şey olduğu doğrulanır; değilse önbelleğe
   YAZILMAZ, böylece bir kez kurulan uygulama engelli ağda bozulmaz. */
function gecerliMi(yanit, istek){
  if(!yanit || !yanit.ok || yanit.type === "opaque") return Promise.resolve(false);
  const yol = new URL(istek.url).pathname;
  const tur = (yanit.headers.get("content-type") || "").toLowerCase();
  if(/\.png$|\.jpe?g$|\.ico$/.test(yol)) return Promise.resolve(tur.indexOf("image/") === 0);
  if(/\.webmanifest$|\.json$/.test(yol)){
    return yanit.clone().text().then(function(t){ try{ JSON.parse(t); return true; }catch(e){ return false; } });
  }
  if(/\.js$/.test(yol)) return Promise.resolve(tur.indexOf("javascript") >= 0);
  if(/\.css$/.test(yol)) return Promise.resolve(tur.indexOf("text/css") >= 0);
  // HTML ya da dizin: gerçekten uygulama mı?
  return yanit.clone().text().then(function(t){ return t.indexOf("bakedEnc") >= 0; });
}

self.addEventListener("fetch", e => {
  const istek = e.request;
  if(istek.method !== "GET") return;
  if(new URL(istek.url).origin !== self.location.origin) return;  // CDN'e karışma

  e.respondWith(
    caches.match(istek, { ignoreSearch: true }).then(onbellek => {
      const ag = fetch(istek).then(yanit =>
        gecerliMi(yanit, istek).then(ok => {
          if(ok) caches.open(AD).then(c => c.put(istek, yanit.clone()));
          return yanit;
        })
      ).catch(() => null);
      return onbellek || ag.then(y => y || new Response("Çevrimdışı", { status: 503 }));
    })
  );
});
