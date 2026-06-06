// Service worker: makes a served datasheet wiki work fully offline.
//
// Strategy: stale-while-revalidate. Each page/asset/image is served instantly
// from the cache when present (so the whole wiki works offline after one visit),
// while a fresh copy is fetched in the background to refresh the cache. The
// cache name carries a per-build id, so rebuilding the wiki invalidates the old
// cache on activate and the new CSS/JS/HTML is picked up on the next load — you
// never get stuck looking at a stale build. (Only active over https:// or
// http://localhost, not file://.)
var CACHE = "datasheet-wiki-__DSW_BUILD__";

self.addEventListener("install", function (e) {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.open(CACHE).then(function (cache) {
      return cache.match(e.request).then(function (hit) {
        var fetched = fetch(e.request).then(function (resp) {
          if (resp && resp.status === 200 && resp.type === "basic") {
            cache.put(e.request, resp.clone());
          }
          return resp;
        }).catch(function () { return hit; });
        // Serve cache immediately when present; always revalidate in background.
        return hit || fetched;
      });
    })
  );
});
