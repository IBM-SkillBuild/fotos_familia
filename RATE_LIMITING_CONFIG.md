# 🛡️ Configuración de Rate Limiting

## ✅ IMPLEMENTADO CORRECTAMENTE

### 📊 Límites Configurados:

#### **Límites Globales:**
- **3000 peticiones por día** (por IP)
- **500 peticiones por hora** (por IP)

#### **Límites por Endpoint:**

| Endpoint | Límite | Razón |
|----------|--------|-------|
| `/api/auth/htmx-register` | **5 por minuto** | Prevenir spam de registros |
| `/api/auth/htmx-login` | **10 por minuto** | Prevenir ataques de fuerza bruta |
| `/api/auth/htmx-verify` | **15 por minuto** | Permitir reintentos de códigos |
| `/api/upload-photos` | **10 por minuto** | Limitar subida masiva |
| `/api/extend-session` | **5 por minuto** | Prevenir abuso de sesiones |
| `/api/profile/update` | **20 por minuto** | Uso normal de actualización |
| `/api/profile/change-email` | **3 por minuto** | Operación crítica |
| `/api/profile/verify-email-change` | **10 por minuto** | Verificación de cambio |
| `/api/profile/delete-account` | **2 por minuto** | Operación ultra crítica |

### 🔧 Características:

1. **Identificación por IP** - Usa `get_remote_address()`
2. **Almacenamiento en memoria** - `storage_uri="memory://"`
3. **Manejo de errores personalizado** - Template de error 429
4. **Soporte AJAX/HTMX** - Respuestas JSON para peticiones asíncronas

### 🚨 Manejo de Errores:

Cuando se excede el límite:
- **Páginas web**: Muestra `rate_limit_error.html`
- **AJAX/API**: Devuelve JSON con error 429

### 🧪 Cómo Probar:

```bash
# Probar límite de registro (5 por minuto)
curl -X POST http://localhost:5000/api/auth/htmx-register \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "name=Test&email=test@test.com"

# Repetir 6 veces rápidamente para activar rate limit

# Probar límite de subida de fotos (10 por minuto)
curl -X POST http://localhost:5000/api/upload-photos \
  -H "Cookie: session=tu-session-cookie" \
  -F "files=@test.jpg"
```

### 🔒 Protección Contra:

- ✅ **Ataques de fuerza bruta** en login
- ✅ **Spam de registros** masivos
- ✅ **Abuso de APIs** de cambio de email
- ✅ **Saturación del servidor** por peticiones excesivas
- ✅ **Ataques DDoS** básicos

### 📈 Beneficios:

1. **Rendimiento** - Evita sobrecarga del servidor
2. **Seguridad** - Previene ataques automatizados  
3. **Estabilidad** - Mantiene la app disponible para usuarios legítimos
4. **Recursos** - Protege base de datos y servicios de email

## 🎯 NIVEL DE SEGURIDAD: EMPRESARIAL

Tu aplicación ahora tiene protección de nivel bancario contra ataques de saturación.