# Configuración de Cloudinary

## 1. Crear cuenta en Cloudinary

1. Ve a [https://cloudinary.com](https://cloudinary.com)
2. Crea una cuenta gratuita
3. Ve al Dashboard

## 2. Obtener credenciales

En el Dashboard de Cloudinary encontrarás:

- **Cloud Name**: Tu nombre de cloud único
- **API Key**: Tu clave de API
- **API Secret**: Tu secreto de API (mantén esto privado)

## 3. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y completa:

```bash
cp .env.example .env
```

Edita el archivo `.env` y agrega tus credenciales:

```env
CLOUDINARY_CLOUD_NAME=tu-cloud-name-aqui
CLOUDINARY_API_KEY=tu-api-key-aqui
CLOUDINARY_API_SECRET=tu-api-secret-aqui
```

## 4. Instalar dependencias

```bash
pip install cloudinary
```

## 5. Estructura de carpetas en Cloudinary

Todas las fotos se organizarán en el folder "familia":
```
familia/
  photo_20241208_143022_abc123.jpg
  photo_20241208_143045_def456.jpg
  photo_20241208_150000_ghi789.jpg
  photo_20241208_151500_jkl012.jpg
```

## 6. Características implementadas

- ✅ Subida automática a Cloudinary
- ✅ Optimización automática de imágenes
- ✅ Conversión a JPG para consistencia
- ✅ Límite de tamaño máximo (1920x1920)
- ✅ Organización por usuario
- ✅ Metadatos de archivo original
- ✅ URLs seguros (HTTPS)
- ✅ Manejo de errores

## 7. Base de datos

El campo `nombre_archivo` ahora guarda la URL de Cloudinary:
```sql
INSERT INTO photos (
  user_id, 
  nombre, 
  nombre_archivo,  -- URL de Cloudinary
  mes, 
  año
) VALUES (
  1, 
  'Mi foto favorita', 
  'https://res.cloudinary.com/tu-cloud/image/upload/v123/familia/photo_20241208_143022_abc123.jpg',
  12, 
  2024
);
```

## 8. Límites del plan gratuito

- 25 GB de almacenamiento
- 25 GB de ancho de banda mensual
- Transformaciones básicas incluidas

¡Perfecto para desarrollo y proyectos pequeños!