#!/usr/bin/env python3
"""
Script para generar imágenes de recorte para personas existentes sin imagen
"""

import sqlite3
import os
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO
import cloudinary
import cloudinary.uploader
import uuid
import json

load_dotenv()

# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

def detect_faces_facepp(image_url):
    """Detectar caras usando Face++ API"""
    try:
        api_key = os.getenv('FACEPP_API_KEY')
        api_secret = os.getenv('FACEPP_API_SECRET')
        
        if not api_key or not api_secret:
            print("❌ Face++ API credentials not configured")
            return []

        data = {
            'api_key': api_key,
            'api_secret': api_secret,
            'image_url': image_url,
            'return_attributes': 'age,gender,emotion'
        }

        response = requests.post('https://api-us.faceplusplus.com/facepp/v3/detect', data=data)
        result = response.json()

        if 'faces' in result:
            return result['faces']
        else:
            print(f"❌ Face++ error: {result}")
            return []

    except Exception as e:
        print(f"❌ Error detectando caras: {e}")
        return []

def crop_face_from_image(image_url, face_rectangle):
    """Recortar cara de una imagen"""
    try:
        # Descargar imagen
        response = requests.get(image_url)
        if response.status_code != 200:
            return None
            
        image = Image.open(BytesIO(response.content))
        
        # Coordenadas del recorte
        left = face_rectangle['left']
        top = face_rectangle['top']
        width = face_rectangle['width']
        height = face_rectangle['height']
        
        # Padding
        padding = int(min(width, height) * 0.1)
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(image.width, left + width + (padding * 2))
        bottom = min(image.height, top + height + (padding * 2))
        
        # Recortar y redimensionar
        face_crop = image.crop((left, top, right, bottom))
        face_crop = face_crop.resize((200, 200), Image.Resampling.LANCZOS)
        
        # Convertir a buffer
        buffer = BytesIO()
        face_crop.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        print(f"❌ Error recortando cara: {e}")
        return None

def upload_face_crop_to_cloudinary(face_crop_buffer, person_name):
    """Subir recorte a Cloudinary"""
    try:
        filename = f"person_{person_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.jpg"
        
        result = cloudinary.uploader.upload(
            face_crop_buffer,
            folder="personas",
            public_id=filename,
            resource_type="image",
            format="jpg"
        )
        
        if result.get('secure_url'):
            return {'success': True, 'url': result['secure_url']}
        else:
            return {'success': False, 'error': 'Invalid Cloudinary response'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def main():
    print("🔧 Generando imágenes para personas sin foto...")
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    # Obtener personas sin imagen
    personas_sin_imagen = conn.execute('''
        SELECT id, nombre FROM personas 
        WHERE imagen IS NULL OR imagen = ''
    ''').fetchall()
    
    print(f"📊 Encontradas {len(personas_sin_imagen)} personas sin imagen")
    
    # Obtener fotos con personas_ids
    fotos_con_personas = conn.execute('''
        SELECT id, nombre_archivo, personas_ids 
        FROM photos 
        WHERE personas_ids IS NOT NULL AND personas_ids != ''
    ''').fetchall()
    
    print(f"📸 Encontradas {len(fotos_con_personas)} fotos con personas etiquetadas")
    
    procesadas = 0
    
    for persona in personas_sin_imagen:
        persona_id = persona['id']
        persona_nombre = persona['nombre']
        
        print(f"\n👤 Procesando: {persona_nombre} (ID: {persona_id})")
        
        # Buscar fotos que contengan esta persona
        foto_encontrada = None
        persona_index = None
        
        for foto in fotos_con_personas:
            try:
                personas_ids = json.loads(foto['personas_ids'])
                if persona_id in personas_ids:
                    foto_encontrada = foto
                    persona_index = personas_ids.index(persona_id)
                    break
            except:
                continue
        
        if not foto_encontrada:
            print(f"⚠️ No se encontró foto para {persona_nombre}")
            continue
            
        print(f"📷 Foto encontrada: {foto_encontrada['nombre_archivo']}")
        print(f"📍 Índice de persona en foto: {persona_index}")
        
        # Detectar caras en la foto
        caras = detect_faces_facepp(foto_encontrada['nombre_archivo'])
        
        if not caras or persona_index >= len(caras):
            print(f"❌ No hay cara en índice {persona_index} (total: {len(caras)})")
            continue
            
        # Recortar cara
        face_rect = caras[persona_index]['face_rectangle']
        face_crop = crop_face_from_image(foto_encontrada['nombre_archivo'], face_rect)
        
        if not face_crop:
            print(f"❌ No se pudo recortar cara para {persona_nombre}")
            continue
            
        # Subir a Cloudinary
        upload_result = upload_face_crop_to_cloudinary(face_crop, persona_nombre)
        
        if upload_result['success']:
            # Actualizar base de datos
            conn.execute('''
                UPDATE personas 
                SET imagen = ? 
                WHERE id = ?
            ''', (upload_result['url'], persona_id))
            
            print(f"✅ {persona_nombre} -> {upload_result['url']}")
            procesadas += 1
        else:
            print(f"❌ Error subiendo {persona_nombre}: {upload_result['error']}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Proceso completado: {procesadas} personas procesadas")

if __name__ == "__main__":
    main()