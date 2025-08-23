// Service Worker para Fotos de Familia PWA
const CACHE_NAME = 'fotos-familia-v1.0.0';
const STATIC_CACHE = 'static-v1.0.0';
const DYNAMIC_CACHE = 'dynamic-v1.0.0';

// Detectar si estamos en desarrollo (localhost)
const isDevelopment = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';

// Archivos estáticos para cachear (solo CDN en desarrollo)
const STATIC_FILES = isDevelopment ? [
  // Solo recursos externos en desarrollo para evitar problemas con localhost
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
  'https://unpkg.com/htmx.org@1.9.10',
  'https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css'
] : [
  // En producción, cachear todo
  '/',
  '/static/css/styles.css',
  '/static/js/store.js',
  '/static/js/paginacion.js',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
  'https://unpkg.com/htmx.org@1.9.10',
  'https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css'
];

// URLs que no deben cachearse
const EXCLUDE_URLS = [
  '/api/',
  '/logout',
  '/auth',
  '/verify'
];

// Instalación del Service Worker
self.addEventListener('install', event => {
  console.log('SW: Instalando Service Worker...', isDevelopment ? '(Modo desarrollo)' : '(Modo producción)');
  
  if (isDevelopment) {
    // En desarrollo, solo cachear recursos externos
    event.waitUntil(
      caches.open(STATIC_CACHE)
        .then(cache => {
          console.log('SW: Cacheando solo recursos externos en desarrollo');
          return cache.addAll(STATIC_FILES).catch(error => {
            console.warn('SW: Algunos recursos no se pudieron cachear:', error);
            // No fallar la instalación por errores de cache en desarrollo
          });
        })
        .then(() => {
          console.log('SW: Service Worker instalado en modo desarrollo');
          return self.skipWaiting();
        })
    );
  } else {
    // En producción, cachear todo
    event.waitUntil(
      caches.open(STATIC_CACHE)
        .then(cache => {
          console.log('SW: Cacheando archivos estáticos');
          return cache.addAll(STATIC_FILES);
        })
        .then(() => {
          console.log('SW: Archivos estáticos cacheados exitosamente');
          return self.skipWaiting();
        })
        .catch(error => {
          console.error('SW: Error cacheando archivos estáticos:', error);
        })
    );
  }
});

// Activación del Service Worker
self.addEventListener('activate', event => {
  console.log('SW: Activando Service Worker...');
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('SW: Eliminando cache obsoleto:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('SW: Service Worker activado');
        return self.clients.claim();
      })
  );
});

// Interceptar peticiones de red
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // En desarrollo, ser más permisivo
  if (isDevelopment) {
    // Solo interceptar recursos externos en desarrollo
    if (!url.origin.includes('localhost') && !url.origin.includes('127.0.0.1')) {
      // Es un recurso externo, usar cache
      event.respondWith(
        caches.match(request)
          .then(response => {
            if (response) {
              return response;
            }
            return fetch(request).catch(() => {
              console.warn('SW: No se pudo cargar recurso externo:', request.url);
            });
          })
      );
    }
    // Para recursos locales en desarrollo, dejar que pasen directamente
    return;
  }

  // No cachear URLs excluidas en producción
  if (EXCLUDE_URLS.some(excludeUrl => url.pathname.startsWith(excludeUrl))) {
    return;
  }

  // Estrategia Cache First para recursos estáticos
  if (request.destination === 'style' || 
      request.destination === 'script' || 
      request.destination === 'font' ||
      url.pathname.startsWith('/static/')) {
    
    event.respondWith(
      caches.match(request)
        .then(response => {
          if (response) {
            console.log('SW: Sirviendo desde cache:', request.url);
            return response;
          }
          
          return fetch(request)
            .then(fetchResponse => {
              if (fetchResponse.ok) {
                const responseClone = fetchResponse.clone();
                caches.open(STATIC_CACHE)
                  .then(cache => {
                    cache.put(request, responseClone);
                  });
              }
              return fetchResponse;
            });
        })
        .catch(() => {
          console.log('SW: Error de red para recurso estático:', request.url);
        })
    );
    return;
  }

  // Estrategia Network First para contenido dinámico
  if (request.method === 'GET' && 
      (url.pathname === '/' || 
       url.pathname.startsWith('/dashboard') ||
       url.pathname.startsWith('/perfil') ||
       url.pathname.startsWith('/selector_fotos'))) {
    
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(DYNAMIC_CACHE)
              .then(cache => {
                cache.put(request, responseClone);
              });
          }
          return response;
        })
        .catch(() => {
          console.log('SW: Sin conexión, buscando en cache:', request.url);
          return caches.match(request)
            .then(response => {
              if (response) {
                return response;
              }
              // Página offline de fallback específica para PWA
              return new Response(`
                <!DOCTYPE html>
                <html lang="es">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Fotos de Familia - Offline</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
                            color: white;
                            margin: 0;
                            padding: 20px;
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            text-align: center;
                        }
                        .container {
                            max-width: 500px;
                        }
                        .icon {
                            font-size: 4rem;
                            margin-bottom: 1rem;
                        }
                        .btn {
                            background: #0d6efd;
                            color: white;
                            border: none;
                            padding: 12px 24px;
                            border-radius: 8px;
                            cursor: pointer;
                            margin: 0.5rem;
                            text-decoration: none;
                            display: inline-block;
                        }
                        .btn:hover {
                            background: #0b5ed7;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">📱</div>
                        <h1>Fotos de Familia</h1>
                        <h2>Modo Offline</h2>
                        <p>No se puede conectar con el servidor. Esto puede pasar si:</p>
                        <ul style="text-align: left; margin: 1rem 0;">
                            <li>El servidor local no está ejecutándose</li>
                            <li>Hay problemas de conectividad</li>
                            <li>La aplicación se instaló desde localhost</li>
                        </ul>
                        <div>
                            <button class="btn" onclick="window.location.reload()">
                                🔄 Reintentar
                            </button>
                            <a class="btn" href="http://localhost:5000" target="_blank">
                                🌐 Abrir en navegador
                            </a>
                        </div>
                        <p style="margin-top: 2rem; opacity: 0.7; font-size: 0.9rem;">
                            Para usar la PWA correctamente, instálala desde un servidor con dominio real (no localhost)
                        </p>
                    </div>
                </body>
                </html>
              `, {
                status: 200,
                headers: { 'Content-Type': 'text/html; charset=utf-8' }
              });
            });
        })
    );
    return;
  }

  // Para imágenes: Cache First con fallback
  if (request.destination === 'image') {
    event.respondWith(
      caches.match(request)
        .then(response => {
          if (response) {
            return response;
          }
          
          return fetch(request)
            .then(fetchResponse => {
              if (fetchResponse.ok) {
                const responseClone = fetchResponse.clone();
                caches.open(DYNAMIC_CACHE)
                  .then(cache => {
                    cache.put(request, responseClone);
                  });
              }
              return fetchResponse;
            })
            .catch(() => {
              // Imagen placeholder offline
              return new Response(
                '<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#f8f9fa"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="#6c757d">Imagen no disponible offline</text></svg>',
                { headers: { 'Content-Type': 'image/svg+xml' } }
              );
            });
        })
    );
  }
});

// Manejar mensajes del cliente
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
});

// Notificaciones push (para futuras implementaciones)
self.addEventListener('push', event => {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-72x72.png',
      vibrate: [100, 50, 100],
      data: {
        dateOfArrival: Date.now(),
        primaryKey: data.primaryKey
      },
      actions: [
        {
          action: 'explore',
          title: 'Ver fotos',
          icon: '/static/icons/icon-96x96.png'
        },
        {
          action: 'close',
          title: 'Cerrar',
          icon: '/static/icons/icon-96x96.png'
        }
      ]
    };
    
    event.waitUntil(
      self.registration.showNotification(data.title, options)
    );
  }
});

// Manejar clicks en notificaciones
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/selector_fotos')
    );
  } else if (event.action === 'close') {
    // Solo cerrar la notificación
  } else {
    // Click en el cuerpo de la notificación
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

console.log('SW: Service Worker cargado correctamente');