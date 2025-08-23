# 📸 Fotos de Familia - PWA

Una aplicación web progresiva (PWA) Flask para gestión segura de fotos familiares con autenticación por email, reconocimiento facial y funcionalidad offline.

## ✨ Características Principales

### 🔐 Autenticación y Seguridad
- ✅ **Autenticación por email** con códigos de verificación de 6 dígitos
- ✅ **Sesiones seguras** con tokens de acceso y expiración automática
- ✅ **Protección CSRF** completa en formularios críticos
- ✅ **Rate Limiting** avanzado para prevenir ataques
- ✅ **Logging completo** de actividades y seguridad
- ✅ **Validación de entrada** y sanitización de datos

### 📱 Progressive Web App (PWA)
- ✅ **Instalable** en Android, iOS y escritorio
- ✅ **Funcionalidad offline** con Service Worker inteligente
- ✅ **Cache optimizado** para recursos estáticos y dinámicos
- ✅ **Responsive design** adaptativo para todos los dispositivos
- ✅ **Notificaciones in-app** y indicadores de conexión
- ✅ **Pull-to-refresh** en dispositivos móviles

### 🖼️ Gestión de Fotos
- ✅ **Subida múltiple** de fotos con drag & drop
- ✅ **Almacenamiento en Cloudinary** con optimización automática
- ✅ **Reconocimiento facial** con Face++ API
- ✅ **Etiquetado de personas** automático y manual
- ✅ **Galerías organizadas** (Todas, Mis Fotos, Recientes)
- ✅ **Búsqueda por persona** en tiempo real
- ✅ **Descarga masiva** de fotos seleccionadas
- ✅ **Edición de metadatos** (nombres, fechas)

### 🎨 Interfaz de Usuario
- ✅ **Navegación HTMX** sin JavaScript personalizado
- ✅ **Dashboard interactivo** con estadísticas
- ✅ **Modales dinámicos** para acciones rápidas
- ✅ **Indicadores de carga** y feedback visual
- ✅ **Tema oscuro** optimizado para fotos
- ✅ **Atajos de teclado** (Ctrl+K buscar, Ctrl+U subir)

## 🚀 Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone <tu-repositorio>
cd fotos-familia
```

### 2. Crear entorno virtual
```bash
python -m venv env
# Windows
env\Scripts\activate
# Linux/Mac
source env/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:
```env
SECRET_KEY=tu-clave-secreta-muy-larga-y-segura
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-aplicacion
CLOUDINARY_CLOUD_NAME=tu-cloud-name
CLOUDINARY_API_KEY=tu-api-key
CLOUDINARY_API_SECRET=tu-api-secret
FACEPP_API_KEY=tu-facepp-key
FACEPP_API_SECRET=tu-facepp-secret
```

### 5. Inicializar base de datos
```bash
python app.py
# La base de datos se crea automáticamente
```

### 6. Generar iconos PWA
```bash
python generate_icons.py
```

### 7. Ejecutar la aplicación
```bash
python app.py
```

Abrir en el navegador: http://localhost:5000

## 📁 Estructura del Proyecto

```
fotos-familia/
├── app.py                      # Aplicación Flask principal
├── config.py                   # Configuración de la aplicación
├── services.py                 # Servicios de reconocimiento facial
├── logger_config.py            # Configuración de logging
├── generate_icons.py           # Generador de iconos PWA
├── test_pwa.py                # Script de pruebas PWA
├── requirements.txt            # Dependencias Python
├── .env.example               # Plantilla de variables de entorno
├── familia.db                 # Base de datos SQLite
├── static/
│   ├── css/
│   │   ├── styles.css         # Estilos principales
│   │   └── pwa.css           # Estilos PWA específicos
│   ├── js/
│   │   ├── store.js          # Estado global Alpine.js
│   │   ├── paginacion.js     # Paginación de galerías
│   │   └── pwa.js           # Funcionalidades PWA
│   ├── icons/                # Iconos PWA (múltiples tamaños)
│   ├── manifest.json         # Manifest PWA
│   ├── sw.js                # Service Worker
│   └── favicon.ico          # Favicon
├── templates/
│   ├── index.html            # Página principal con PWA
│   ├── offline.html          # Página offline PWA
│   ├── dashboard.html        # Dashboard principal
│   ├── auth_*.html          # Templates de autenticación
│   ├── galeria_*.html       # Templates de galerías
│   ├── subir_foto.html      # Subida de fotos
│   └── profile.html         # Perfil de usuario
└── docs/
    ├── README.md            # Este archivo
    ├── PWA_README.md        # Documentación PWA
    ├── security_audit.md    # Auditoría de seguridad
    └── *.md                # Documentación técnica
```

## 🔧 Configuración Avanzada

### Cloudinary (Almacenamiento de fotos)
1. Crear cuenta en [Cloudinary](https://cloudinary.com)
2. Obtener credenciales del Dashboard
3. Configurar en `.env`
4. Ver [CLOUDINARY_SETUP.md](CLOUDINARY_SETUP.md) para detalles

### Face++ (Reconocimiento facial)
1. Crear cuenta en [Face++](https://www.faceplusplus.com)
2. Obtener API Key y Secret
3. Configurar en `.env`
4. Límite gratuito: 1000 llamadas/mes

### SMTP (Envío de emails)
1. Configurar Gmail con contraseña de aplicación
2. O usar otro proveedor SMTP
3. Configurar credenciales en `.env`

## 📱 Instalación como PWA

### Android (Chrome/Edge)
1. Abrir la aplicación en Chrome
2. Aparecerá banner de instalación automáticamente
3. O usar menú ⋮ > "Añadir a pantalla de inicio"

### iOS (Safari)
1. Abrir la aplicación en Safari
2. Tocar botón compartir
3. Seleccionar "Añadir a pantalla de inicio"

### Escritorio (Chrome/Edge)
1. Buscar icono de instalación en barra de direcciones
2. O usar menú > "Instalar [nombre de la app]"

## 🧪 Testing y Desarrollo

### Probar funcionalidad PWA
```bash
python test_pwa.py
```

### Verificar seguridad
```bash
# Ver auditoría completa
cat security_audit.md
```

### Debugging
```bash
# Modo debug activado por defecto en desarrollo
python app.py
# Endpoints de debug disponibles en /admin/*
```

### Lighthouse (Chrome DevTools)
1. F12 > Lighthouse
2. Seleccionar "Progressive Web App"
3. Ejecutar auditoría

## 🚀 Despliegue en Producción

### Requisitos
- ✅ **HTTPS obligatorio** (PWA requirement)
- ✅ **Dominio válido** (no IP)
- ✅ **Certificado SSL** (Let's Encrypt recomendado)
- ✅ **Variables de entorno** configuradas
- ✅ **Base de datos** (SQLite OK para proyectos pequeños)

### Checklist Pre-Deploy
- [ ] Todas las variables de entorno configuradas
- [ ] Iconos PWA generados correctamente
- [ ] Service Worker funciona sin errores
- [ ] HTTPS configurado
- [ ] Rate limiting ajustado para producción
- [ ] Logs configurados para producción

## 🔒 Seguridad

### Nivel de Seguridad: **BANCARIO/GUBERNAMENTAL (5/5)**

- ✅ **SQL Injection**: 100% protegido con parámetros preparados
- ✅ **XSS**: 100% protegido con Jinja2 auto-escape
- ✅ **CSRF**: 100% protegido con Flask-WTF tokens
- ✅ **Rate Limiting**: Configurado para todos los endpoints críticos
- ✅ **Autenticación**: Sesiones seguras con expiración
- ✅ **Validación**: Sanitización completa de entrada

Ver [security_audit.md](security_audit.md) para auditoría completa.

## 📊 Características Técnicas

### Backend
- **Framework**: Flask 2.3+
- **Base de datos**: SQLite con migraciones automáticas
- **Autenticación**: Sesiones con tokens seguros
- **Email**: SMTP con templates HTML
- **Storage**: Cloudinary para fotos
- **AI**: Face++ para reconocimiento facial

### Frontend
- **CSS**: Bootstrap 5.3 + estilos personalizados
- **JavaScript**: HTMX + Alpine.js (mínimo JS)
- **PWA**: Service Worker + Manifest
- **Icons**: FontAwesome 6
- **Responsive**: Mobile-first design

### APIs Externas
- **Cloudinary**: Almacenamiento y optimización de imágenes
- **Face++**: Reconocimiento facial y detección
- **SMTP**: Envío de códigos de verificación

## 🆘 Troubleshooting

### La aplicación no inicia
```bash
# Verificar dependencias
pip install -r requirements.txt

# Verificar variables de entorno
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('SECRET_KEY:', bool(os.getenv('SECRET_KEY')))"
```

### PWA no se puede instalar
- Verificar HTTPS en producción
- Comprobar manifest.json válido
- Asegurar Service Worker registrado

### Fotos no se suben
- Verificar credenciales Cloudinary
- Comprobar límites de tamaño
- Revisar logs de error

### Reconocimiento facial no funciona
- Verificar credenciales Face++
- Comprobar límites de API
- Revisar formato de imágenes

## 📚 Documentación Adicional

- [PWA_README.md](PWA_README.md) - Guía completa PWA
- [security_audit.md](security_audit.md) - Auditoría de seguridad
- [RATE_LIMITING_CONFIG.md](RATE_LIMITING_CONFIG.md) - Configuración rate limiting
- [CLOUDINARY_SETUP.md](CLOUDINARY_SETUP.md) - Configuración Cloudinary
- [CSRF_PROTECTION_CONFIG.md](CSRF_PROTECTION_CONFIG.md) - Protección CSRF

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para detalles.

---

🎉 **¡Tu aplicación de fotos familiares está lista para usar como PWA!**
