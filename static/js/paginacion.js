// back-button-handler.js
(function() {
    // 1. Variables de configuración
    const TARGET_PAGE = '/';
    let enabled = true;
    
    // 2. Configuración inicial discreta
    if (!window.history.state?.isAppControlled) {
        window.history.replaceState({ isAppControlled: true }, '');
    }
    
    // 3. Manejador de eventos no obstructivo
    const handlePopState = (event) => {
        if (!enabled) return;
        
        if (!event.state?.isAppControlled) {
            window.history.replaceState({ isAppControlled: true }, '', TARGET_PAGE);
            if (window.location.pathname !== TARGET_PAGE) {
                window.location.assign(TARGET_PAGE);
            }
        }
    };
    
    // 4. Registro del evento con opciones pasivas
    window.addEventListener('popstate', handlePopState, { passive: true });
    
    // 5. API mínima para control externo
    window.backNavigation = {
        setEnabled: (state) => { enabled = state; },
        setTargetPage: (path) => { TARGET_PAGE = path; }
    };
})();