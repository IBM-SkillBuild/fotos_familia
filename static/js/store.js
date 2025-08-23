/**
 * Alpine.js Store Global para Email Auth App
 */

document.addEventListener("alpine:init", () => {
 // Reemplazar el estado actual para evitar historial futuro
history.replaceState(null, null, window.location.href);

// Añadir una entrada al historial
history.pushState(null, null, window.location.href);

// Escuchar el evento popstate
window.onpopstate = function(event) {
  history.pushState(null, null, window.location.href);
};
  Alpine.store("app", {
    // Store listo para futuras funcionalidades
    prueba: "estado inicial",
  });
});
