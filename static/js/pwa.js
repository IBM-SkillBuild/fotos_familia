// Funcionalidades PWA adicionales
class PWAManager {
  constructor() {
    this.isOnline = navigator.onLine;
    this.installPrompt = null;
    this.init();
  }

  init() {
    this.setupConnectionMonitoring();
    this.setupInstallPrompt();
    this.setupPullToRefresh();
    this.setupKeyboardShortcuts();
    this.setupNotifications();
  }

  // Monitoreo de conexión
  setupConnectionMonitoring() {
    const showConnectionStatus = (online) => {
      const existing = document.querySelector('.connection-status');
      if (existing) existing.remove();

      const status = document.createElement('div');
      status.className = `connection-status ${online ? 'online' : 'offline'}`;
      status.innerHTML = online 
        ? '<i class="fas fa-wifi me-1"></i>Conectado' 
        : '<i class="fas fa-wifi-slash me-1"></i>Sin conexión';
      
      document.body.appendChild(status);
      
      setTimeout(() => {
        if (status.parentNode) {
          status.remove();
        }
      }, 3000);
    };

    window.addEventListener('online', () => {
      this.isOnline = true;
      showConnectionStatus(true);
      console.log('PWA: Conexión restaurada');
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      showConnectionStatus(false);
      console.log('PWA: Conexión perdida');
    });
  }

  // Configurar prompt de instalación
  setupInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.installPrompt = e;
      this.showInstallButton();
    });

    window.addEventListener('appinstalled', () => {
      console.log('PWA: App instalada');
      this.hideInstallButton();
      this.showNotification('¡App instalada exitosamente!', 'success');
    });
  }

  showInstallButton() {
    if (document.getElementById('pwa-install-btn')) return;

    const button = document.createElement('button');
    button.id = 'pwa-install-btn';
    button.className = 'btn btn-success position-fixed';
    button.style.cssText = `
      bottom: 20px; 
      right: 20px; 
      z-index: 1050; 
      border-radius: 50px;
      padding: 12px 20px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    button.innerHTML = '<i class="fas fa-download me-2"></i>Instalar App';
    button.onclick = () => this.installApp();

    document.body.appendChild(button);
  }

  hideInstallButton() {
    const button = document.getElementById('pwa-install-btn');
    if (button) button.remove();
  }

  async installApp() {
    if (!this.installPrompt) return;

    const result = await this.installPrompt.prompt();
    console.log('PWA: Resultado instalación:', result.outcome);

    if (result.outcome === 'accepted') {
      this.hideInstallButton();
    }

    this.installPrompt = null;
  }

  // Pull to refresh
  setupPullToRefresh() {
    let startY = 0;
    let currentY = 0;
    let pulling = false;

    document.addEventListener('touchstart', (e) => {
      if (window.scrollY === 0) {
        startY = e.touches[0].clientY;
        pulling = true;
      }
    });

    document.addEventListener('touchmove', (e) => {
      if (!pulling) return;

      currentY = e.touches[0].clientY;
      const pullDistance = currentY - startY;

      if (pullDistance > 0 && pullDistance < 100) {
        e.preventDefault();
        this.showPullToRefresh(pullDistance);
      }
    });

    document.addEventListener('touchend', () => {
      if (pulling && currentY - startY > 80) {
        this.triggerRefresh();
      }
      this.hidePullToRefresh();
      pulling = false;
    });
  }

  showPullToRefresh(distance) {
    let element = document.querySelector('.ptr-element');
    if (!element) {
      element = document.createElement('div');
      element.className = 'ptr-element';
      element.innerHTML = '<i class="fas fa-sync-alt"></i> Desliza para actualizar';
      document.body.appendChild(element);
    }

    const progress = Math.min(distance / 80, 1);
    element.style.transform = `translateY(${-100 + (progress * 100)}%)`;
    
    if (progress >= 1) {
      element.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Suelta para actualizar';
    }
  }

  hidePullToRefresh() {
    const element = document.querySelector('.ptr-element');
    if (element) {
      element.style.transform = 'translateY(-100%)';
      setTimeout(() => {
        if (element.parentNode) {
          element.remove();
        }
      }, 300);
    }
  }

  triggerRefresh() {
    this.showNotification('Actualizando...', 'info');
    setTimeout(() => {
      window.location.reload();
    }, 500);
  }

  // Atajos de teclado
  setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Ctrl/Cmd + K para búsqueda rápida
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[name="buscar_persona"]');
        if (searchInput) {
          searchInput.focus();
        }
      }

      // Ctrl/Cmd + U para subir foto
      if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        const uploadBtn = document.querySelector('[onclick="subirFoto()"]');
        if (uploadBtn) {
          uploadBtn.click();
        }
      }

      // Escape para cerrar modales
      if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
          const closeBtn = modal.querySelector('[data-bs-dismiss="modal"]');
          if (closeBtn) closeBtn.click();
        });
      }
    });
  }

  // Sistema de notificaciones
  setupNotifications() {
    // Solicitar permisos de notificación si están disponibles
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(permission => {
        console.log('PWA: Permisos de notificación:', permission);
      });
    }
  }

  showNotification(message, type = 'info', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `pwa-notification ${type} show`;
    notification.innerHTML = `
      <div class="d-flex align-items-center">
        <i class="fas fa-${this.getIconForType(type)} me-2"></i>
        <span>${message}</span>
        <button type="button" class="btn-close btn-close-white ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
      </div>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.classList.remove('show');
      notification.classList.add('hide');
      setTimeout(() => {
        if (notification.parentNode) {
          notification.remove();
        }
      }, 300);
    }, duration);
  }

  getIconForType(type) {
    const icons = {
      success: 'check-circle',
      error: 'exclamation-circle',
      warning: 'exclamation-triangle',
      info: 'info-circle'
    };
    return icons[type] || 'info-circle';
  }

  // Utilidades
  isPWA() {
    return window.matchMedia('(display-mode: standalone)').matches || 
           window.navigator.standalone === true;
  }

  getInstallationStatus() {
    return {
      isPWA: this.isPWA(),
      canInstall: !!this.installPrompt,
      isOnline: this.isOnline
    };
  }

  // Método para mostrar información de la PWA
  showPWAInfo() {
    const status = this.getInstallationStatus();
    const info = `
      PWA Status:
      - Instalada: ${status.isPWA ? 'Sí' : 'No'}
      - Puede instalarse: ${status.canInstall ? 'Sí' : 'No'}
      - En línea: ${status.isOnline ? 'Sí' : 'No'}
    `;
    console.log(info);
    return status;
  }
}

// Inicializar PWA Manager cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  window.pwaManager = new PWAManager();
  
  // Añadir clase PWA si está ejecutándose como app instalada
  if (window.pwaManager.isPWA()) {
    document.documentElement.classList.add('pwa-mode');
  }
});

// Funciones globales para compatibilidad
window.showPWANotification = (message, type, duration) => {
  if (window.pwaManager) {
    window.pwaManager.showNotification(message, type, duration);
  }
};

window.getPWAStatus = () => {
  return window.pwaManager ? window.pwaManager.showPWAInfo() : null;
};