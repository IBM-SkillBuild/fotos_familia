
import os
import requests
import base64
from io import BytesIO
from PIL import Image, ImageOps
import cloudinary
import cloudinary.uploader
import secrets

# Configurar Cloudinary (asumiendo que se carga desde env en app.py, pero repetimos por independencia)
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

def detect_faces_facepp(image_url):
    """
    Detecta caras en una imagen usando Face++ API con URL de imagen.
    Retorna lista de caras detectadas o None en error.
    """
    api_key = os.getenv('FACEPP_API_KEY')
    api_secret = os.getenv('FACEPP_API_SECRET')
    
    if not api_key or not api_secret:
        print("⚠️ Face++ credentials not configured")
        return None
    
    data = {
        'api_key': api_key,
        'api_secret': api_secret,
        'image_url': image_url,
        'return_attributes': 'age,gender'
    }
    
    try:
        response = requests.post(
            'https://api-us.faceplusplus.com/facepp/v3/detect',
            data=data,
            timeout=15  # Reducido de 30 a 15 segundos
        )
        result = response.json()
        
        if 'faces' in result:
            return result['faces']
        else:
            print(f"⚠️ No faces detected or error: {result.get('error_message', 'Unknown')}")
            return None
            
    except Exception as e:
        print(f"❌ Error in detect_faces_facepp: {e}")
        return None

def get_face_crop(image_url, face_rectangle):
    """
    Recorta la cara de la imagen usando PIL basado en el rectángulo proporcionado.
    Retorna buffer BytesIO con la imagen recortada o None en error.
    """
    try:
        response = requests.get(image_url, timeout=10)  # Timeout para descarga de imagen
        if response.status_code != 200:
            print(f"⚠️ Error downloading image: {response.status_code}")
            return None
        
        image = Image.open(BytesIO(response.content))
        
        left = face_rectangle['left']
        top = face_rectangle['top']
        width = face_rectangle['width']
        height = face_rectangle['height']
        
        # Añadir padding para mejor encuadre
        padding = int(min(width, height) * 0.1)
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(image.width, left + width + 2 * padding)
        bottom = min(image.height, top + height + 2 * padding)
        
        crop = image.crop((left, top, right, bottom))
        crop = crop.resize((200, 200), Image.Resampling.LANCZOS)
        
        buffer = BytesIO()
        crop.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        print(f"❌ Error in get_face_crop: {e}")
        return None

def get_face_crop_from_facepp(image_url, face_token):
    """
    Obtiene recorte de cara usando la API de thumbnail de Face++.
    Nota: image_url podría no ser necesario, pero se incluye por compatibilidad con la llamada en app.py.
    Retorna bytes del recorte o None en error.
    """
    api_key = os.getenv('FACEPP_API_KEY')
    api_secret = os.getenv('FACEPP_API_SECRET')
    
    if not api_key or not api_secret:
        print("⚠️ Face++ credentials not configured")
        return None
    
    data = {
        'api_key': api_key,
        'api_secret': api_secret,
        'face_token': face_token,
        'thumbnail_rate': 1.0  # Tamaño completo relativo al rostro detectado
    }
    
    try:
        response = requests.post(
            'https://api-us.faceplusplus.com/facepp/v3/face/thumbnail',
            data=data,
            timeout=15  # Reducido de 30 a 15 segundos
        )
        result = response.json()
        
        if 'thumbnail' in result:
            return base64.b64decode(result['thumbnail'])
        else:
            print(f"⚠️ No thumbnail or error: {result.get('error_message', 'Unknown')}")
            return None
            
    except Exception as e:
        print(f"❌ Error in get_face_crop_from_facepp: {e}")
        return None

def upload_temp_face_crop(buffer):
    """
    Sube un recorte temporal de cara a Cloudinary en carpeta temp_faces.
    Retorna dict con secure_url y public_id o dict con error.
    """
    try:
        public_id = f"temp_face_{secrets.token_hex(8)}"
        
        result = cloudinary.uploader.upload(
            buffer,
            folder="temp_faces",
            public_id=public_id,
            resource_type="image",
            format="jpg",
            quality="auto:low",  # Reducir calidad para mayor velocidad
            transformation=[
                {"width": 200, "height": 200, "crop": "fill"}  # Optimizar tamaño
            ],
            timeout=10  # Timeout de 10 segundos
        )
        
        return {
            'secure_url': result['secure_url'],
            'public_id': result['public_id']
        }
        
    except Exception as e:
        print(f"❌ Error in upload_temp_face_crop: {e}")
        return {'error': str(e)}

def upload_face_crop_to_cloudinary(face_crop, nombre):
    """
    Sube recorte de cara a Cloudinary en carpeta personas.
    face_crop puede ser bytes o BytesIO.
    Retorna dict con success, url y public_id.
    """
    try:
        if isinstance(face_crop, bytes):
            buffer = BytesIO(face_crop)
        else:
            buffer = face_crop
            buffer.seek(0)
        
        public_id = f"person_face_{nombre.replace(' ', '_')}_{secrets.token_hex(4)}"
        
        result = cloudinary.uploader.upload(
            buffer,
            folder="personas",
            public_id=public_id,
            resource_type="image",
            format="jpg",
            quality="auto:good",
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"}
            ]
        )
        
        return {
            'success': True,
            'url': result['secure_url'],
            'public_id': result['public_id']
        }
        
    except Exception as e:
        print(f"❌ Error in upload_face_crop_to_cloudinary: {e}")
        return {'success': False, 'error': str(e)}
