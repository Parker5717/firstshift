/**
 * FirstShift Service Worker
 *
 * Отвечает за:
 * 1. Кэширование статики (HTML, CSS, JS) при установке
 * 2. Офлайн-очередь Safety Check через IndexedDB + Background Sync
 */

const CACHE_NAME   = 'firstshift-v2';
const SYNC_TAG     = 'safety-check-sync';
const IDB_NAME     = 'firstshift-offline';
const IDB_STORE    = 'safety_queue';

// Статика которую кэшируем при установке
const STATIC_ASSETS = [
  '/',
  '/app',
  '/safety',
  '/profile',
  '/encyclopedia',
  '/markers',
  '/static/css/main.css',
  '/static/css/hud.css',
  '/static/js/api.js',
  '/static/js/app.js',
  '/static/js/camera.js',
  '/static/js/ar-overlay.js',
  '/static/js/xp-bar.js',
  '/static/js/quest-engine.js',
  '/static/js/vision-client.js',
  '/static/js/achievements.js',
  '/static/js/speedrun.js',
  '/static/js/quiz.js',
  '/static/js/mascot.js',
  '/static/js/onboarding.js',
];

// ── Установка: кэшируем статику ──────────────────────────────────────────────
self.addEventListener('install', event => {
  console.log('[SW] Установка...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        // Кэшируем по одному — не падаем если один ресурс недоступен
        return Promise.allSettled(
          STATIC_ASSETS.map(url =>
            cache.add(url).catch(e => console.warn('[SW] Не удалось кэшировать:', url, e.message))
          )
        );
      })
      .then(() => {
        console.log('[SW] Статика кэширована');
        return self.skipWaiting();
      })
  );
});

// ── Активация: чистим старые кэши ────────────────────────────────────────────
self.addEventListener('activate', event => {
  console.log('[SW] Активация...');
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => { console.log('[SW] Удаляем старый кэш:', k); return caches.delete(k); })
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: отдаём из кэша или сети ───────────────────────────────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API-запросы — только сеть (не кэшируем динамику)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) {
    return; // браузер обработает сам
  }

  // Статика — cache-first
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        if (cached) return cached;
        return fetch(event.request)
          .then(response => {
            // Кэшируем успешные GET-ответы
            if (response.ok && event.request.method === 'GET') {
              const clone = response.clone();
              caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
            }
            return response;
          })
          .catch(() => {
            // Сеть недоступна — возвращаем кэш для HTML страниц
            if (event.request.headers.get('accept')?.includes('text/html')) {
              return caches.match('/');
            }
          });
      })
  );
});

// ── Background Sync: отправляем очередь Safety Check ─────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === SYNC_TAG) {
    console.log('[SW] Background Sync: отправляем очередь Safety Check...');
    event.waitUntil(flushSafetyQueue());
  }
});

async function flushSafetyQueue() {
  const db    = await openIDB();
  const items = await getAllFromStore(db, IDB_STORE);

  if (!items.length) {
    console.log('[SW] Очередь пуста');
    return;
  }

  console.log('[SW] Записей в очереди:', items.length);

  for (const item of items) {
    try {
      const resp = await fetch('/api/progress/safety_check', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${item.token}`,
        },
        body: JSON.stringify({
          helmet:    item.helmet,
          vest:      item.vest,
          goggles:   item.goggles,
          client_id: item.client_id,
        }),
      });

      if (resp.ok || resp.status === 409) {
        // Успешно или уже записано (дубликат) — удаляем из очереди
        await deleteFromStore(db, IDB_STORE, item.id);
        console.log('[SW] Safety Check отправлен и удалён из очереди:', item.client_id);

        // Уведомляем клиент
        const clients = await self.clients.matchAll();
        clients.forEach(c => c.postMessage({
          type:      'safety_check_synced',
          client_id: item.client_id,
        }));
      } else {
        console.warn('[SW] Сервер вернул', resp.status, '— оставляем в очереди');
      }
    } catch (e) {
      console.error('[SW] Ошибка отправки Safety Check:', e.message);
      // Сеть ещё недоступна — прекращаем, попробуем при следующем sync
      break;
    }
  }
}

// ── IndexedDB хелперы ─────────────────────────────────────────────────────────

function openIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function getAllFromStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function deleteFromStore(db, storeName, id) {
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = e => reject(e.target.error);
  });
}
