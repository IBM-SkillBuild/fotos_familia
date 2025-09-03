from logger_config import (
    app_logger, log_request, log_response, log_error,
    log_user_action, log_session_event, log_database_operation
)
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from flask_wtf import FlaskForm
from config import Config
from flask import Flask, abort, render_template, request, jsonify, session, redirect, url_for,g
import psycopg2
import secrets
import hashlib
import json
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import base64
from io import BytesIO
import time
import socket
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import detect_faces_facepp, get_face_crop, upload_face_crop_to_cloudinary, upload_temp_face_crop, get_face_crop_from_facepp
# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()
from whitenoise import WhiteNoise
from werkzeug.middleware.proxy_fix import ProxyFix

import multiprocessing

# Número de workers
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4 # Añadido para manejar más peticiones concurrentes

# Timeouts
timeout = 300  # 120 segundos
keepalive = 5

# Graceful restart settings
max_requests = 1000
max_requests_jitter = 100

# Logs
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Worker class
worker_class = "sync"

# Configurar Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    timeout=60,
    secure=True
)

app = Flask(__name__, static_folder='static')

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)
app.config.from_object(Config)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/',prefix='static/')

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # 1 hora
socket.setdefaulttimeout(120)  # 120 segundos
app.config['WTF_CSRF_ENABLED'] = False  # Desactivar CSRF para pruebas
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Configurar Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["3000 per day", "500 per hour"],
    storage_uri="memory://"
)

# Configurar protección CSRF
csrf = CSRFProtect(app)

# Configuración de la base de datos PostgreSQL
DATABASE_CONFIG = {
    'host': os.getenv('DATABASE_HOST', 'ep-divine-sea-a2tsh7q5.eu-central-1.pg.koyeb.app'),
    'database': os.getenv('DATABASE_NAME', 'koyebdb'),
    'user': os.getenv('DATABASE_USER', 'koyeb-adm'),
    'password': os.getenv('DATABASE_PASSWORD', 'npg_dGpMKX9j8qnm'),
    'port': os.getenv('DATABASE_PORT', '5432'),
    'connect_timeout': 10,
    'sslmode': 'require'
}
app_logger.info(f"Using PostgreSQL database: {DATABASE_CONFIG['host']}")

def get_db():
    """Obtener conexión a la base de datos PostgreSQL"""
    if 'db' not in g:
        try:
            app_logger.info(f"Conectando a PostgreSQL con host: {DATABASE_CONFIG['host']}")
            g.db = psycopg2.connect(
                host=DATABASE_CONFIG['host'],
                database=DATABASE_CONFIG['database'],
                user=DATABASE_CONFIG['user'],
                password=DATABASE_CONFIG['password'],
                port=DATABASE_CONFIG['port'],
                connect_timeout=DATABASE_CONFIG.get('connect_timeout', 10),
                sslmode=DATABASE_CONFIG.get('sslmode', 'require')
            )
            g.db.autocommit = True
            app_logger.info("Conexión a PostgreSQL establecida exitosamente")
        except psycopg2.OperationalError as e:
            app_logger.error(f"Error de conexión operacional a PostgreSQL: {str(e)}")
            raise
        except psycopg2.DatabaseError as e:
            app_logger.error(f"Error de base de datos en PostgreSQL: {str(e)}")
            raise
        except Exception as e:
            app_logger.error(f"Error inesperado conectando a PostgreSQL: {str(e)}")
            raise
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    """Cerrar la conexión a la base de datos al final de la petición"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inicializar la base de datos PostgreSQL"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Crear tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                alias TEXT,
                phone TEXT,
                email TEXT,
                access_token TEXT,
                token_expires TIMESTAMP,
                verification_code TEXT,
                code_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_interaction_days INTEGER DEFAULT 1
            )
        ''')

        # Crear tabla de sesiones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                token TEXT UNIQUE,
                expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Crear tabla de códigos de verificación
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                name TEXT,
                code TEXT NOT NULL,
                expires TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Crear tabla de fotos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                nombre TEXT,
                nombre_archivo TEXT NOT NULL,
                categoria TEXT,
                mes INTEGER,
                año INTEGER,
                personas_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Crear tabla de personas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                imagen TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Crear tabla para solicitudes de cambio de email
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_change_requests (
                user_id INTEGER PRIMARY KEY,
                new_email TEXT NOT NULL,
                verification_code TEXT NOT NULL,
                expires TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Crear tabla para verificaciones de email
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verification (
                email TEXT PRIMARY KEY,
                name TEXT,
                code TEXT,
                expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Crear índices para optimizar consultas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON verification_codes(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verification_codes_code ON verification_codes(code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_año ON photos(año)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_mes ON photos(mes)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_personas_nombre ON personas(nombre)')

        conn.commit()
        app_logger.info("PostgreSQL database initialized successfully")
        
    except Exception as e:
        app_logger.error(f"Error initializing PostgreSQL database: {str(e)}")
        raise

# Manejo de errores de rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    """Manejo personalizado de errores de rate limiting"""
    if request.headers.get('HX-Request') or request.headers.get('Content-Type') == 'application/json':
        return jsonify({
            'error': True,
            'message': 'Demasiadas peticiones. Intenta más tarde.',
            'retry_after': e.retry_after
        }), 429

    return render_template('rate_limit_error.html',
                           description=e.description,
                           retry_after=e.retry_after), 429

def create_user_email(name, email):
    """Crear nuevo usuario con email en la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (name, email, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (name, email, datetime.now(), datetime.now()))

        user_id = cursor.fetchone()[0]
        conn.commit()
        log_database_operation('INSERT', 'users', f'Email: {email}, ID: {user_id}')
        return user_id

    except psycopg2.IntegrityError as e:
        log_error('create_user_email', e, f'Email: {email}')
        return None
    except Exception as e:
        log_error('create_user_email', e, f'Email: {email}')
        return None

def create_user_session_email(user_id):
    """Crear sesión segura para usuario autenticado con email"""
    try:
        access_token = secrets.token_urlsafe(32)
        token_expires = datetime.now() + timedelta(hours=8)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET access_token = %s, token_expires = %s, updated_at = %s
            WHERE id = %s
        ''', (access_token, token_expires, datetime.now(), user_id))
        conn.commit()

        # Configurar sesión
        session.permanent = True
        session['user_id'] = user_id
        session['access_token'] = access_token

        log_database_operation('UPDATE', 'users', f'Session created for user {user_id}')
        return access_token

    except Exception as e:
        log_error('create_user_session_email', e, f'User ID: {user_id}')
        return None

def store_verification_code(email, name, code):
    """Almacenar código de verificación en la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        expires = datetime.now() + timedelta(minutes=10)  # Código válido por 10 minutos

        # Limpiar códigos anteriores para este email
        cursor.execute('DELETE FROM verification_codes WHERE email = %s', (email,))

        # Insertar nuevo código
        cursor.execute('''
            INSERT INTO verification_codes (email, name, code, expires)
            VALUES (%s, %s, %s, %s)
        ''', (email, name, code, expires))

        conn.commit()
        log_database_operation('INSERT', 'verification_codes', f'Email: {email}')
        return True

    except Exception as e:
        log_error('store_verification_code', e, f'Email: {email}')
        return False

def verify_code(email, code):
    """Verificar código de verificación desde la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Buscar código válido
        cursor.execute('''
            SELECT name FROM verification_codes 
            WHERE email = %s AND code = %s AND expires > %s
        ''', (email, code, datetime.now()))
        result = cursor.fetchone()

        if result:
            # Limpiar código usado
            cursor.execute('DELETE FROM verification_codes WHERE email = %s AND code = %s', (email, code))
            conn.commit()
            log_database_operation('DELETE', 'verification_codes', f'Email: {email}, Code verified')
            return result[0]  # PostgreSQL devuelve tuplas

        return None

    except Exception as e:
        log_error('verify_code', e, f'Email: {email}')
        return None

def cleanup_expired_codes():
    """Limpiar códigos de verificación expirados"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM verification_codes WHERE expires <= %s', (datetime.now(),))
        deleted_count = cursor.rowcount
        conn.commit()

        if deleted_count > 0:
            log_database_operation('DELETE', 'verification_codes', f'Cleaned {deleted_count} expired codes')

    except Exception as e:
        log_error('cleanup_expired_codes', e, 'Cleanup failed')

def update_interaction_days(user_id):
    """Actualiza los días de interacción del usuario."""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Obtener la última fecha de interacción y los días totales
        cursor.execute(
            "SELECT last_interaction_date, total_interaction_days FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()

        if result:
            last_interaction_date_str = result[0]
            total_interaction_days = result[1]

            last_interaction_date = last_interaction_date_str
            today = datetime.now().date()

            if last_interaction_date.date() < today:
                # Si la última interacción fue en un día diferente, incrementar el contador
                total_interaction_days += 1
                cursor.execute("UPDATE users SET last_interaction_date = %s, total_interaction_days = %s WHERE id = %s",
                               (datetime.now(), total_interaction_days, user_id))
                conn.commit()
                app_logger.info(
                    f"User {user_id}: Interaction days updated to {total_interaction_days}")
            else:
                app_logger.info(
                    f"User {user_id}: Interaction already logged for today.")

    except Exception as e:
        app_logger.error(
            f"Error updating interaction days for user {user_id}: {e}")

def upload_to_cloudinary(file, user_id, original_filename):
    """Subir archivo a Cloudinary y retornar URL"""
    try:
        # Generar un public_id único para evitar conflictos
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        public_id = f"photo_{timestamp}_{secrets.token_hex(4)}"

        # Subir a Cloudinary - siempre usar folder "familia"
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            folder="familia",
            resource_type="image",
            format="jpg",  # Convertir todo a JPG para consistencia
            quality="auto:good",  # Optimización automática
            fetch_format="auto",  # Formato automático según el navegador
            transformation=[
                # Limitar tamaño máximo
                {"width": 1920, "height": 1920, "crop": "limit"},
                {"quality": "auto:good"}
            ],
            context={
                "original_filename": original_filename,
                "user_id": str(user_id),
                "upload_date": datetime.now().isoformat()
            }
        )

        return {
            'success': True,
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'width': result.get('width'),
            'height': result.get('height'),
            'format': result.get('format'),
            'bytes': result.get('bytes')
        }

    except Exception as e:
        print(f"Error subiendo a Cloudinary: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def delete_from_cloudinary(public_id):
    """Eliminar foto de Cloudinary"""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"Error eliminando de Cloudinary: {e}")
        return False

def send_verification_email(email, code, name="Usuario"):
    """Enviar código de verificación por email"""
    try:
        # Configuración SMTP desde variables de entorno
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_email = os.getenv('SMTP_EMAIL')
        smtp_password = os.getenv('SMTP_PASSWORD')
        smtp_from_name = os.getenv('SMTP_FROM_NAME', 'Auth App')

        if not all([smtp_server, smtp_email, smtp_password]):
            print("Configuracion SMTP incompleta")
            return False

        # Crear mensaje HTML
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{smtp_from_name} <{smtp_email}>"
        msg['To'] = email
        msg['Subject'] = f"Tu código de verificación: {code}"

        # Cuerpo del email en HTML elegante
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0 0 20px 0; font-size: 24px; font-weight: 300;">
                        🔐 Código de Verificación
                    </h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">
                        Hola {name}, aquí tienes tu código
                    </p>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                        Has solicitado acceso a tu cuenta. Usa el siguiente código para completar la verificación:
                    </p>
                    
                    <!-- Code Box -->
                    <div style="border: 2px dashed #3498db; border-radius: 10px; padding: 30px; text-align: center; background: #f8f9ff; margin: 30px 0;">
                        <div style="font-size: 36px; font-weight: bold; color: #3498db; letter-spacing: 8px; margin-bottom: 10px;">
                            {code}
                        </div>
                        <p style="color: #999; margin: 0; font-size: 14px;">
                            Código de 6 dígitos
                        </p>
                    </div>
                    
                    <!-- Warning -->
                    <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <p style="color: #856404; margin: 0; font-size: 14px;">
                            ⏰ Este código expira en 10 minutos
                        </p>
                    </div>
                    
                    <p style="color: #666; font-size: 14px; line-height: 1.6; margin-top: 30px;">
                        Si no solicitaste este código, puedes ignorar este email.
                    </p>
                </div>
                
                <!-- Footer -->
                <div style="background: #f8f9fa; padding: 20px 30px; text-align: center; border-top: 1px solid #eee;">
                    <p style="color: #999; margin: 0; font-size: 12px;">
                        © 2024 {smtp_from_name} - Sistema de Autenticación Segura
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        # Texto plano como fallback
        text_body = f"""
Hola {name},

Tu código de verificación es: {code}

Este código expira en 10 minutos.

Si no solicitaste este código, puedes ignorar este email.

Saludos,
{smtp_from_name}
        """

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Enviar email
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()

        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()

        print(f"Email enviado a {email}")
        return True

    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

def get_user_display_name(user):
    """Obtener el mejor nombre disponible para mostrar"""
    if not user:
        return 'Usuario'
    return user['name'] or 'Usuario'

def require_auth(f):
    """Decorador para requerir autenticación en endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            # Si es una petición AJAX/HTMX, usar HX-Location para mantener SPA
            if request.headers.get('HX-Request') or request.headers.get('Content-Type') == 'application/json':
                redirect_location = {
                    "path": url_for('index'),
                    "target": "body",
                    "swap": "innerHTML"
                }
                return '', 200, {'HX-Location': json.dumps(redirect_location)}
            # Si es una petición normal, redirigir al login
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def require_debug(f):
    """Decorador para requerir modo debug"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not app.debug:
            return "Solo disponible en modo debug", 403
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Obtener usuario actual de la sesión"""
    if 'user_id' not in session or 'access_token' not in session:
        return None

    user_id = session['user_id']
    access_token = session['access_token']

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users 
        WHERE id = %s AND access_token = %s AND token_expires > %s
    ''', (user_id, access_token, datetime.now()))
    user_row = cursor.fetchone()
    
    if user_row:
        # Convert row to dict
        columns = [desc[0] for desc in cursor.description]
        user = dict(zip(columns, user_row))
        return user
    else:
        # Limpiar sesión inválida
        session.clear()
        return None

@app.route('/health')
def health_check():
    return {'status': 'healthy'}, 200

@app.route('/')
def index():
    user = get_current_user()  # Get user to check if logged in
    if user:
        update_interaction_days(user['id'])  # Update interaction days

    # Siempre renderizar el index.html base
    return render_template('index.html')

# === RUTAS PWA ===
@app.route('/static/manifest.json')
def manifest():
    """Servir el manifest.json para PWA"""
    return app.send_static_file('manifest.json')

@app.route('/static/sw.js')
def service_worker():
    """Servir el service worker"""
    response = app.send_static_file('sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/offline')
def offline():
    """Página offline para PWA"""
    return render_template('offline.html') if os.path.exists('templates/offline.html') else '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sin conexión - Fotos de Familia</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #0f0f23; color: white; }
            .offline-icon { font-size: 4rem; margin-bottom: 20px; }
            .retry-btn { background: #0d6efd; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="offline-icon">📱</div>
        <h1>Sin conexión</h1>
        <p>No hay conexión a internet. Algunas funciones pueden no estar disponibles.</p>
        <button class="retry-btn" onclick="window.location.reload()">Reintentar</button>
    </body>
    </html>
    '''

@app.route('/initial-content')
def initial_content():
    # Verificar si el usuario ya está autenticado
    user = get_current_user()
    if user:
        # Usuario autenticado → cargar panel principal
        return render_template('main_panel_content.html', user=user)
    else:
        # Usuario no autenticado → cargar página de auth
        return render_template('auth_page_content.html')

@app.route('/auth-modal')
def auth_modal():
    """Cargar el formulario de autenticación simple"""
    return render_template('auth_simple.html')

@app.route('/auth-login-form')
def auth_login_form():
    """Mostrar formulario de login"""
    return render_template('auth_login_form.html')

@app.route('/auth-register-form')
def auth_register_form():
    """Mostrar formulario de registro"""
    return render_template('auth_register_form.html')

@app.route('/auth-verify-error')
def auth_verify_error():
    """Mostrar formulario de verificación con error"""
    email = request.args.get('email', '')
    error_type = request.args.get('error', '')

    if error_type == 'codigo_incorrecto':
        error_msg = "Código incorrecto o expirado"
    else:
        error_msg = "Email y código son requeridos"

    return render_template('auth_verify_code.html',
                           email=email,
                           error=error_msg,
                           flow_type='login')

@app.route('/navbar-content')
@require_auth
def navbar_content():
    """Devolver solo el navegador"""
    user = get_current_user()
    return render_template('navbar_content.html', user=user)

@app.route('/cargar_navegador')
@require_auth
def cargar_navegador():
    """Devolver solo el navegador"""
    user = get_current_user()
    return render_template('navbar_content.html', user=user)

@app.route('/dashboard-main')
@require_auth
def dashboard_main():
    """Devolver solo el contenido principal del dashboard"""
    user = get_current_user()
    return render_template('dashboard_main_content.html', user=user)

def is_htmx_request():
    """Detectar si es una petición HTMX"""
    return request.headers.get('HX-Request') == 'true'

def get_form_data():
    """Obtener datos del formulario o JSON"""
    if request.content_type and 'application/json' in request.content_type:
        return request.get_json() or {}
    else:
        return request.form.to_dict()

@app.route('/api/auth/htmx-register', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def htmx_register():
    """Wrapper HTMX para registro que guarda código directamente"""
    try:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()

        if not name or not email:
            return render_template('auth_register_form.html')

        # Verificar que el email no exista
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return render_template('auth_user_exists.html', email=email)

        # Generar código de verificación
        verification_code = str(secrets.randbelow(900000) + 100000)
        code_expires = datetime.now() + timedelta(minutes=10)

        print(
            f"DEBUG REGISTER: Generando código '{verification_code}' para {email}")
        print(f"DEBUG REGISTER: Expira en: {code_expires}")

        # Crear usuario temporal con código
        cursor.execute('''
            INSERT INTO users (name, email, verification_code, code_expires, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (name, email, verification_code, code_expires, datetime.now(), datetime.now()))

        user_id = cursor.fetchone()[0]
        conn.commit()

        # Enviar código por email
        email_sent = send_verification_email(email, verification_code, name)
        if not email_sent:
            print(
                f"⚠️ No se pudo enviar email a {email}, pero continuando con el proceso")

        # Mostrar verificación
        return render_template('auth_verify_simple.html', email=email, flow_type='register')

    except Exception as e:
        log_error('htmx_register', e, f'Name: {name}, Email: {email}')
        return render_template('auth_register_form.html')

@app.route('/api/auth/htmx-login', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def htmx_login():
    """Wrapper HTMX para login que guarda código directamente"""
    app_logger.info('htmx_login function started')
    try:
        email = request.form.get('email', '').strip()

        if not email:
            return render_template('auth_login_form.html')

        # Verificar que el email existe
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if not existing_user:
            return render_template('auth_user_not_found.html', email=email)

        # Generar código de verificación
        verification_code = str(secrets.randbelow(900000) + 100000)
        code_expires = datetime.now() + timedelta(minutes=10)

        print(
            f"DEBUG LOGIN: Generando código '{verification_code}' para {email}")
        print(f"DEBUG LOGIN: Expira en: {code_expires}")

        # Actualizar usuario con código
        cursor.execute('''
            UPDATE users 
            SET verification_code = %s, code_expires = %s, updated_at = %s
            WHERE email = %s
        ''', (verification_code, code_expires, datetime.now(), email))

        conn.commit()

        # Enviar código por email
        email_sent = send_verification_email(
            email, verification_code, existing_user[1])
        if not email_sent:
            print(
                f"⚠️ No se pudo enviar email a {email}, pero continuando con el proceso")

        # Mostrar verificación
        return render_template('auth_verify_simple.html', email=email, flow_type='login')

    except Exception as e:
        log_error('htmx_login', e, f'Email: {email}')
        return render_template('auth_login_form.html', error="Error interno del servidor. Inténtalo de nuevo.")

@app.route('/api/auth/htmx-verify', methods=['POST'])
@csrf.exempt
@limiter.limit("15 per minute")
def htmx_verify():
    """Wrapper HTMX para verificación que crea sesión directamente"""
    email = None
    try:
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()

        app_logger.info(
            f"DEBUG VERIFY: Iniciando verificación para email='{email}', code='{code}'")
        app_logger.info(f"DEBUG VERIFY: Form data: {dict(request.form)}")

        if not email or not code:
            app_logger.warning(
                f"DEBUG VERIFY: Faltan datos - email='{email}', code='{code}'")
            return render_template('auth_verify_simple.html',
                                   email=email,
                                   error="Email y código son requeridos",
                                   flow_type='login')

        # Verificar código directamente en la base de datos
        app_logger.info("Obteniendo conexión a la base de datos")
        conn = get_db()
        cursor = conn.cursor()
        app_logger.info("Conexión a la base de datos obtenida exitosamente")

        # Primero buscar el usuario por email para debug
        app_logger.info(f"Buscando usuario con email: {email}")
        cursor.execute('''
            SELECT id, name, email, verification_code, code_expires 
            FROM users 
            WHERE email = %s
        ''', (email,))
        debug_user = cursor.fetchone()
        app_logger.info(
            f"DEBUG VERIFY: Usuario encontrado: {debug_user if debug_user else 'None'}")

        if debug_user:
            app_logger.info(f"DEBUG VERIFY: Código recibido: '{code}'")
            app_logger.info(
                f"DEBUG VERIFY: Código en DB: '{debug_user[3] if debug_user else 'None'}'")
            app_logger.info(
                f"DEBUG VERIFY: Expira en: {debug_user[4] if debug_user else 'None'}")
        app_logger.info(f"DEBUG VERIFY: Hora actual: {datetime.now()}")

        app_logger.info("Verificando código de verificación")
        cursor.execute('''
            SELECT id, name, verification_code, code_expires 
            FROM users 
            WHERE email = %s AND verification_code = %s AND code_expires > %s
        ''', (email, code, datetime.now()))
        user = cursor.fetchone()
        app_logger.info(f"Resultado de verificación: {user is not None}")

        if not user:
            app_logger.warning(f"Código incorrecto o expirado para email {email}")
            return render_template('auth_verify_simple.html',
                                   email=email,
                                   error="Código incorrecto o expirado",
                                   flow_type='login')

        # Limpiar código de verificación
        app_logger.info("Limpiando código de verificación")
        cursor.execute('''
            UPDATE users 
            SET verification_code = NULL, code_expires = NULL, updated_at = %s
            WHERE id = %s
        ''', (datetime.now(), user[0]))
        conn.commit()
        app_logger.info("Código de verificación limpiado exitosamente")

        user_id = user[0]

        # Crear sesión
        app_logger.info(f"Creando sesión para usuario {user_id}")
        access_token = create_user_session_email(user_id)
        if not access_token:
            app_logger.error(f"Error creando sesión para usuario {user_id}")
            return render_template('auth_verify_simple.html',
                                   email=email,
                                   error="Error creando sesión",
                                   flow_type='login')
        app_logger.info("Sesión creada exitosamente")

        log_user_action(user_id, 'LOGIN_SUCCESS', f'Email: {email}')

        # Retornar template de éxito
        app_logger.info("Retornando auth_success.html")
        return render_template('auth_success.html')

    except psycopg2.OperationalError as e:
        app_logger.error(f'Error de conexión a la base de datos para email {email}: {str(e)}')
        return render_template('auth_verify_simple.html',
                               email=email,
                               error="Error de conexión a la base de datos. Inténtalo de nuevo.",
                               flow_type='login')
    except psycopg2.DatabaseError as e:
        app_logger.error(f'Error de base de datos para email {email}: {str(e)}')
        return render_template('auth_verify_simple.html',
                               email=email,
                               error="Error en la base de datos. Inténtalo de nuevo.",
                               flow_type='login')
    except Exception as e:
        app_logger.error(f'htmx_verify error for email {email}: {str(e)}', exc_info=True)
        return render_template('auth_verify_simple.html',
                               email=email,
                               error="Error al verificar el código. Inténtalo de nuevo.",
                               flow_type='login')

@app.route('/debug-session')
def debug_session():
    """Endpoint para debuggear la sesión"""
    if not app.debug:
        return "Solo disponible en modo debug", 403

    return jsonify({
        'session_data': dict(session),
        'session_keys': list(session.keys()),
        'has_verification_code': 'verification_code' in session,
        'has_verification_email': 'verification_email' in session
    })

@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        # Si es HTMX, mantener SPA
        if request.headers.get('HX-Request'):
            redirect_location = {
                "path": url_for('index'),
                "target": "body",
                "swap": "innerHTML"
            }
            return '', 200, {'HX-Location': json.dumps(redirect_location)}
        return redirect(url_for('index'))

    update_interaction_days(user['id'])  # Update interaction days

    # Preparar información de sesión
    if user['token_expires']:
        # Verificar si token_expires ya es un objeto datetime o es una cadena
        if isinstance(user['token_expires'], str):
            expires = datetime.fromisoformat(user['token_expires'])
        else:
            # Si ya es un objeto datetime, usarlo directamente
            expires = user['token_expires']
            
        time_left = expires - datetime.now()
        total_minutes = int(time_left.total_seconds() / 60)

        if total_minutes <= 0:
            session_time_info = {
                'minutes_remaining': 0,
                'hours_remaining': 0,
                'mins_remaining': 0,
                'is_expiring_soon': True
            }
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60

            session_time_info = {
                'minutes_remaining': total_minutes,
                'hours_remaining': hours,
                'mins_remaining': minutes,
                'is_expiring_soon': total_minutes < 30
            }
    else:
        session_time_info = {
            'minutes_remaining': 0,
            'hours_remaining': 0,
            'mins_remaining': 0,
            'is_expiring_soon': True
        }

    # Formatear la fecha de expiración correctamente
    if user['token_expires']:
        if isinstance(user['token_expires'], str):
            expires_at = user['token_expires'][:19] if len(user['token_expires']) > 19 else user['token_expires']
        else:
            # Si es un objeto datetime, formatearlo
            expires_at = user['token_expires'].strftime('%Y-%m-%d %H:%M:%S')
    else:
        expires_at = 'No definido'
        
    # Formatear la fecha de creación correctamente
    if user['created_at']:
        if isinstance(user['created_at'], str):
            created_at = user['created_at'][:19] if len(user['created_at']) > 19 else user['created_at']
        else:
            # Si es un objeto datetime, formatearlo
            created_at = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    else:
        created_at = 'No definido'

    session_info = {
        'expires_at': expires_at,
        'user_id': user['id'],
        'created_at': created_at,
        **session_time_info  # Agregar la información de tiempo
    }

    # Si es una petición HTMX, devolver solo el contenido del dashboard
    if request.headers.get('HX-Request'):
        return render_template('dashboard_content.html', user=user, session_info=session_info)

    # Dashboard original completo
    log_user_action(user['id'], 'VIEW_DASHBOARD', 'Dashboard accessed')
    return render_template('dashboard.html', user=user, session_info=session_info)

@app.route('/main')
def main_panel():
    """Template principal con navegación cuando hay sesión activa"""
    user = get_current_user()
    if not user:
        # Si es HTMX, mantener SPA
        if request.headers.get('HX-Request'):
            redirect_location = {
                "path": url_for('index'),
                "target": "body",
                "swap": "innerHTML"
            }
            return '', 200, {'HX-Location': json.dumps(redirect_location)}
        return redirect(url_for('index'))

    log_user_action(user['id'], 'VIEW_MAIN_PANEL', 'Main panel accessed')
    return render_template('main_panel.html', user=user)

@app.route('/dashboard-content')
@require_auth
def dashboard_content():
    """Contenido del dashboard para cargar con HTMX"""
    user = get_current_user()

    # Preparar información de sesión (reutilizar lógica)
    if user['token_expires']:
        # Verificar si token_expires ya es un objeto datetime o es una cadena
        if isinstance(user['token_expires'], str):
            expires = datetime.fromisoformat(user['token_expires'])
        else:
            # Si ya es un objeto datetime, usarlo directamente
            expires = user['token_expires']
            
        time_left = expires - datetime.now()
        total_minutes = int(time_left.total_seconds() / 60)

        if total_minutes <= 0:
            session_time_info = {
                'minutes_remaining': 0,
                'hours_remaining': 0,
                'mins_remaining': 0,
                'is_expiring_soon': True
            }
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60

            session_time_info = {
                'minutes_remaining': total_minutes,
                'hours_remaining': hours,
                'mins_remaining': minutes,
                'is_expiring_soon': total_minutes < 30
            }
    else:
        session_time_info = {
            'minutes_remaining': 0,
            'hours_remaining': 0,
            'mins_remaining': 0,
            'is_expiring_soon': True
        }

    # Formatear la fecha de expiración correctamente
    if user['token_expires']:
        if isinstance(user['token_expires'], str):
            expires_at = user['token_expires'][:19] if len(user['token_expires']) > 19 else user['token_expires']
        else:
            # Si es un objeto datetime, formatearlo
            expires_at = user['token_expires'].strftime('%Y-%m-%d %H:%M:%S')
    else:
        expires_at = 'No definido'
        
    # Formatear la fecha de creación correctamente
    if user['created_at']:
        if isinstance(user['created_at'], str):
            created_at = user['created_at'][:19] if len(user['created_at']) > 19 else user['created_at']
        else:
            # Si es un objeto datetime, formatearlo
            created_at = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    else:
        created_at = 'No definido'

    session_info = {
        'expires_at': expires_at,
        'user_id': user['id'],
        'created_at': created_at,
        **session_time_info
    }

    log_user_action(user['id'], 'VIEW_DASHBOARD_CONTENT',
                    'Dashboard content loaded')
    return render_template('dashboard_content.html', user=user, session_info=session_info)


@app.route('/profile-content')
@require_auth
def profile_content():
    """Contenido del perfil para cargar con HTMX"""
    user = get_current_user()
    log_user_action(user['id'], 'VIEW_PROFILE_CONTENT',
                    'Profile content loaded')
    return render_template('profile.html', user=user)

@app.route('/selector_fotos')
@require_auth
def selector_fotos():
    """Selector de fotos"""
    user = get_current_user()

    return render_template('opciones.html', user=user)

respuestas_correctas = [
    "paquita",
    "carlos",
    "fernando",
    "gloria",
    "maripaz"
]

@app.route('/api/verificar_respuesta', methods=['POST'])
def verificar_respuesta():
    """Verifica la respuesta de la pregunta de seguridad."""
    # Obtener el índice de la pregunta y la respuesta del formulario
    question_index = request.form.get('question_index', type=int)
    respuesta_usuario = request.form.get('respuesta', '').lower().strip()

    # Validar el índice
    if question_index is None or question_index < 0 or question_index >= len(respuestas_correctas):
        abort(400, description="Índice de pregunta inválido")

    # Verificar la respuesta
    if respuesta_usuario == respuestas_correctas[question_index]:
        return render_template('opciones.html')
    else:
        return render_template('error_de_pregunta.html')

@app.route('/subir_foto')
@require_auth
def subir_foto():
    """Formulario para subir foto"""
    user = get_current_user()
    return render_template('subir_foto.html', user=user)

@app.route('/api/upload-photos', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def upload_photos():
    """API para subir fotos a Cloudinary y guardar metadatos en BD"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': True, 'message': 'Usuario no autenticado'}), 401

        # Verificar que hay archivos
        if 'files' not in request.files:
            return jsonify({'error': True, 'message': 'No se enviaron archivos'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': True, 'message': 'No se seleccionaron archivos'}), 400

        # Obtener metadatos de cada foto
        nombres = request.form.getlist('nombres')
        nombres_archivo_originales = request.form.getlist('nombres_archivo')
        meses = request.form.getlist('meses')
        años = request.form.getlist('años')

        uploaded_photos = []
        failed_uploads = []
        conn = get_db()
        cursor = conn.cursor()

        for i, file in enumerate(files):
            if file and file.filename:
                # Validar tipo de archivo
                if not file.content_type.startswith('image/'):
                    failed_uploads.append({
                        'filename': file.filename,
                        'error': 'Tipo de archivo no válido'
                    })
                    continue

                # Obtener metadatos para esta foto
                nombre = nombres[i] if i < len(nombres) else None
                nombre_archivo_original = nombres_archivo_originales[i] if i < len(
                    nombres_archivo_originales) else file.filename
                mes = int(meses[i]) if i < len(meses) and meses[i] else None
                año = int(años[i]) if i < len(años) and años[i] else None

                # Subir a Cloudinary
                print(f"Subiendo {file.filename} a Cloudinary...")
                cloudinary_result = upload_to_cloudinary(
                    file, user['id'], nombre_archivo_original)

                if not cloudinary_result['success']:
                    failed_uploads.append({
                        'filename': file.filename,
                        'error': cloudinary_result['error']
                    })
                    continue

                # Guardar en base de datos con URL de Cloudinary
                cursor.execute('''
                    INSERT INTO photos (user_id, nombre, nombre_archivo, mes, año, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (user['id'], nombre, cloudinary_result['url'], mes, año, datetime.now(), datetime.now()))

                photo_id = cursor.fetchone()[0]
                uploaded_photos.append({
                    'id': photo_id,
                    'nombre': nombre,
                    'nombre_archivo_original': nombre_archivo_original,
                    'cloudinary_url': cloudinary_result['url'],
                    'cloudinary_public_id': cloudinary_result['public_id'],
                    'mes': mes,
                    'año': año,
                    'width': cloudinary_result.get('width'),
                    'height': cloudinary_result.get('height'),
                    'format': cloudinary_result.get('format'),
                    'size_bytes': cloudinary_result.get('bytes')
                })

                print(f"Foto {file.filename} subida exitosamente")

        conn.commit()

        # Preparar respuesta
        success_count = len(uploaded_photos)
        failed_count = len(failed_uploads)

        message = f'Se subieron {success_count} fotos exitosamente'
        if failed_count > 0:
            message += f', {failed_count} fallaron'

        log_user_action(user['id'], 'UPLOAD_PHOTOS',
                        f'Uploaded {success_count} photos, {failed_count} failed')

        return jsonify({
            'success': True,
            'message': message,
            'uploaded_photos': uploaded_photos,
            'failed_uploads': failed_uploads,
            'stats': {
                'success_count': success_count,
                'failed_count': failed_count,
                'total_count': success_count + failed_count
            }
        })

    except Exception as e:
        log_error('upload_photos', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'error': True, 'message': 'Error interno del servidor'}), 500

@app.route('/fotos-recien-subidas')
@require_auth
def fotos_recien_subidas():
    """Mostrar solo las fotos que se acaban de subir"""
    try:
        user = get_current_user()

        # Obtener IDs de fotos desde la query string
        foto_ids = request.args.get('ids', '').split(',')
        foto_ids = [id.strip() for id in foto_ids if id.strip().isdigit()]

        if not foto_ids:
            return render_template('galeria_todas_fotos.html', fotos=[], user=user)

        conn = get_db()
        cursor = conn.cursor()

        # Crear placeholders para la consulta SQL
        placeholders = ','.join(['%s' for _ in foto_ids])

        # Obtener solo las fotos recién subidas
        cursor.execute(f'''
            SELECT p.*, u.name as usuario_nombre
            FROM photos p
            JOIN users u ON p.user_id = u.id
            WHERE p.id IN ({placeholders})
            ORDER BY p.created_at DESC
        ''', foto_ids)
        fotos = cursor.fetchall()

        # Convertir a lista de diccionarios
        fotos_list = []
        columns = [desc[0] for desc in cursor.description]
        for foto in fotos:
            foto_dict = dict(zip(columns, foto))
            # Determinar si necesita etiquetado
            personas_ids = foto_dict['personas_ids']
            necesita_etiquetado = (
                not personas_ids or
                personas_ids == 'null' or
                personas_ids == '' or
                personas_ids == '[]' or
                personas_ids == 'None'
            )

            fotos_list.append({
                'id': foto_dict['id'],
                'nombre': foto_dict['nombre'],
                'nombre_archivo': foto_dict['nombre_archivo'],
                'mes': foto_dict['mes'],
                'año': foto_dict['año'],
                'usuario_nombre': foto_dict['usuario_nombre'],
                'created_at': foto_dict['created_at'],
                'personas_ids': foto_dict['personas_ids'],
                'necesita_etiquetado': necesita_etiquetado
            })

        log_user_action(user['id'], 'VIEW_RECENT_UPLOADS',
                        f'Viewed {len(fotos_list)} recently uploaded photos')

        return render_template('galeria_fotos_recientes.html',
                               fotos=fotos_list,
                               user=user)

    except Exception as e:
        log_error('fotos_recien_subidas', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return render_template('error.html', message='Error al cargar las fotos recientes'), 500

@app.route('/editar_nombre')
@require_auth
def editar_nombre():
    """Muestra el formulario para editar el nombre de una foto, reemplazando el panel principal."""
    user = get_current_user()
    photo_id = request.args.get('id', type=int)

    if not photo_id:
        return '<div class="alert alert-danger m-3">ID de foto no proporcionado.</div>', 400

    conn = get_db()
    cursor = conn.cursor()
    # Asegurarse de que el usuario solo pueda editar sus propias fotos
    cursor.execute(
        'SELECT id, nombre, nombre_archivo, mes, año FROM photos WHERE id = %s AND user_id = %s',
        (photo_id, user['id'])
    )
    foto = cursor.fetchone()

    if not foto:
        return '<div class="alert alert-danger m-3">Foto no encontrada o no tienes permiso para editarla.</div>', 404

    # Convertir a dict
    columns = [desc[0] for desc in cursor.description]
    foto_dict = dict(zip(columns, foto))

    return render_template('editar_nombre.html', foto=foto_dict)

@app.route('/api/actualizar_nombre/<int:photo_id>', methods=['POST'])
@require_auth
def actualizar_nombre(photo_id):
    """Actualiza el nombre de una foto."""
    user = get_current_user()

    conn = get_db()
    cursor = conn.cursor()
    # Verificar que la foto pertenece al usuario
    cursor.execute(
        'SELECT id FROM photos WHERE id = %s AND user_id = %s',
        (photo_id, user['id'])
    )
    foto = cursor.fetchone()

    if not foto:
        return '<div class="alert alert-danger">Foto no encontrada o sin permiso.</div>', 404

    try:
        nuevo_nombre = request.form.get('nombre', '').strip()
        if not nuevo_nombre:
            return '<div class="alert alert-danger">El nombre no puede estar vacío.</div>', 400

        cursor.execute(
            'UPDATE photos SET nombre = %s, updated_at = %s WHERE id = %s',
            (nuevo_nombre, datetime.now(), photo_id)
        )
        conn.commit()

        log_user_action(user['id'], 'UPDATE_PHOTO_NAME',
                        f'Updated photo ID: {photo_id} to name: {nuevo_nombre}')

        return '<div class="alert alert-success">Nombre actualizado correctamente.</div>'

    except Exception as e:
        log_error('actualizar_nombre', e,
                  f'User: {user["id"]}, Photo ID: {photo_id}')
        return f'<div class="alert alert-danger">Error al actualizar: {e}</div>', 500

@app.route('/settings-content')
@require_auth
def settings_content():
    """Contenido de configuración para cargar con HTMX"""
    user = get_current_user()
    log_user_action(user['id'], 'VIEW_SETTINGS_CONTENT',
                    'Settings content loaded')
    return '''
    <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
        <h1 class="h2">Configuración</h1>
    </div>
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">Configuración de la Cuenta</h5>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        Esta sección estará disponible próximamente.
                    </div>
                    
                    <h6>Opciones disponibles:</h6>
                    <ul class="list-unstyled">
                        <li class="mb-2">
                            <i class="fas fa-bell text-primary me-2"></i>
                            Notificaciones por email
                        </li>
                        <li class="mb-2">
                            <i class="fas fa-shield-alt text-success me-2"></i>
                            Configuración de seguridad
                        </li>
                        <li class="mb-2">
                            <i class="fas fa-palette text-warning me-2"></i>
                            Tema de la aplicación
                        </li>
                        <li class="mb-2">
                            <i class="fas fa-language text-info me-2"></i>
                            Idioma de la interfaz
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    '''

@app.route('/activity-content')
@require_auth
def activity_content():
    """Contenido de actividad para cargar con HTMX"""
    user = get_current_user()
    log_user_action(user['id'], 'VIEW_ACTIVITY_CONTENT',
                    'Activity content loaded')
    return '''
    <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
        <h1 class="h2">Actividad Reciente</h1>
    </div>
    
    <div class="row">
        <div class="col-md-10">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">Historial de Actividad</h5>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <i class="fas fa-history me-2"></i>
                        Esta sección mostrará tu actividad reciente próximamente.
                    </div>
                    
                    <div class="timeline">
                        <div class="timeline-item">
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6 class="mb-1">Sesión iniciada</h6>
                                <small class="text-muted">Hace unos minutos</small>
                            </div>
                        </div>
                        
                        <div class="timeline-item">
                            <div class="timeline-marker bg-primary"></div>
                            <div class="timeline-content">
                                <h6 class="mb-1">Perfil actualizado</h6>
                                <small class="text-muted">Ejemplo de actividad</small>
                            </div>
                        </div>
                        
                        <div class="timeline-item">
                            <div class="timeline-marker bg-warning"></div>
                            <div class="timeline-content">
                                <h6 class="mb-1">Email verificado</h6>
                                <small class="text-muted">Ejemplo de actividad</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <style>
    .timeline {
        position: relative;
        padding-left: 30px;
    }
    
    .timeline::before {
        content: '';
        position: absolute;
        left: 15px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #dee2e6;
    }
    
    .timeline-item {
        position: relative;
        margin-bottom: 20px;
    }
    
    .timeline-marker {
        position: absolute;
        left: -22px;
        top: 5px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 0 0 2px #dee2e6;
    }
    
    .timeline-content {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 3px solid #007bff;
    }
    </style>
    '''

@app.route('/api/profile/update', methods=['POST'])
@limiter.limit("20 per minute")
@require_auth
def update_profile():
    """Actualizar información del perfil"""
    user = get_current_user()

    try:
        data = request.form
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()

        log_user_action(user['id'], 'UPDATE_PROFILE_ATTEMPT',
                        f'Name: {name}, Phone: {phone}')

        if not name:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> El nombre es requerido.
            </div>
            '''

        # Actualizar información (solo nombre y teléfono)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET name = %s, phone = %s, updated_at = %s
            WHERE id = %s
        ''', (name, phone if phone else None, datetime.now(), user['id']))
        conn.commit()

        log_user_action(user['id'], 'UPDATE_PROFILE_SUCCESS',
                        f'Updated: {name}, {phone}')
        log_database_operation(
            'UPDATE', 'users', f'Profile updated for user {user["id"]}')

        return '''
        <div class="alert alert-success">
            <strong>¡Éxito!</strong> Tu perfil ha sido actualizado correctamente.
        </div>
        '''

    except Exception as e:
        log_error('update_profile', e, f'User ID: {user["id"]}')
        return '''
        <div class="alert alert-danger">
            <strong>Error:</strong> No se pudo actualizar el perfil. Inténtalo de nuevo.
        </div>
        '''

@app.route('/api/profile/activity')
@require_auth
def profile_activity():
    """Obtener actividad reciente del usuario"""
    user = get_current_user()

    # Simular actividad reciente (en una app real, esto vendría de logs)
    activities = [
        {
            'action': 'Inicio de sesión',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'icon': '🔑',
            'description': 'Acceso exitoso al sistema'
        },
        {
            'action': 'Perfil visitado',
            'timestamp': (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
            'icon': '👤',
            'description': 'Página de perfil accedida'
        },
        {
            'action': 'Cuenta creada',
            'timestamp': user['created_at'][:19] if user['created_at'] else 'No disponible',
            'icon': '🎉',
            'description': 'Registro completado exitosamente'
        }
    ]

    activity_html = ''
    for activity in activities:
        activity_html += f'''
        <div class="d-flex align-items-center mb-3 p-2 border-start border-primary border-3">
            <div class="me-3 fs-4">{activity['icon']}</div>
            <div class="flex-grow-1">
                <div class="fw-bold">{activity['action']}</div>
                <small class="text-muted">{activity['description']}</small>
                <div class="small text-secondary">{activity['timestamp']}</div>
            </div>
        </div>
        '''

    if not activity_html:
        activity_html = '''
        <div class="text-center text-muted">
            <div class="mb-2">📝</div>
            <p>No hay actividad reciente registrada.</p>
        </div>
        '''

    return activity_html

@app.route('/profile/change-email')
@require_auth
def change_email_modal():
    """Cargar modal para cambiar email"""
    user = get_current_user()
    return render_template('change_email_modal.html', user=user)

@app.route('/profile/delete-account')
@require_auth
def delete_account_modal():
    """Cargar modal para eliminar cuenta"""
    user = get_current_user()
    log_user_action(user['id'], 'DELETE_MODAL_OPENED',
                    'User opened delete account modal')

    try:
        # Estadísticas simples para evitar errores
        user_stats = {
            'days_active': 1,  # Valor por defecto
            'email_requests': 0,
            'verification_count': 0,
            'has_phone': bool(user['phone']) if user['phone'] else False
        }

        # Intentar calcular días reales
        try:
            if user['created_at']:
                created = datetime.fromisoformat(user['created_at'])
                user_stats['days_active'] = max(
                    1, (datetime.now() - created).days)
        except:
            pass  # Usar valor por defecto

        # Intentar contar registros relacionados
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT COUNT(*) as count FROM email_change_requests WHERE user_id = %s',
                (user['id'],))
            email_requests_row = cursor.fetchone()
            if email_requests_row:
                user_stats['email_requests'] = email_requests_row[0]

        except:
            pass  # Usar valores por defecto

        app_logger.info(
            f"Delete modal loaded for user {user['id']} - Stats: {user_stats}")
        return render_template('delete_account_modal.html', user=user, stats=user_stats)

    except Exception as e:
        log_error('delete_account_modal', e, f'User ID: {user["id"]}')
        return '''
        <div class="alert alert-danger">
            <strong>Error:</strong> No se pudo cargar el modal. Inténtalo de nuevo.
        </div>
        '''

@app.route('/profile/delete-account-page')
@require_auth
def delete_account_page():
    """Cargar página completa para eliminar cuenta"""
    user = get_current_user()
    log_user_action(user['id'], 'DELETE_PAGE_OPENED',
                    'User opened delete account page')

    try:
        # Estadísticas simples
        user_stats = {
            'days_active': 1,
            'email_requests': 0,
            'verification_count': 0,
            'has_phone': bool(user['phone']) if user['phone'] else False
        }

        # Calcular días reales
        try:
            if user['created_at']:
                created = datetime.fromisoformat(user['created_at'])
                user_stats['days_active'] = max(
                    1, (datetime.now() - created).days)
        except:
            pass

        app_logger.info(
            f"Delete page loaded for user {user['id']} - Stats: {user_stats}")
        return render_template('delete_account_page.html', user=user, stats=user_stats)

    except Exception as e:
        log_error('delete_account_page', e, f'User ID: {user["id"]}')
        return '''
        <div class="container mt-4">
            <div class="alert alert-danger">
                <strong>Error:</strong> No se pudo cargar la página. 
                <button class="btn btn-link p-0" hx-get="/profile" hx-target="#main-content" hx-swap="innerHTML">
                    Volver al perfil
                </button>
            </div>
        </div>
        '''

@app.route('/api/profile/change-email', methods=['POST'])
@limiter.limit("3 per minute")
def request_email_change():
    """Solicitar cambio de email - enviar código de verificación"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'No autenticado'}), 401

    try:
        data = request.form
        new_email = data.get('new_email', '').strip()
        confirm_email = data.get('confirm_email', '').strip()

        log_user_action(user['id'], 'EMAIL_CHANGE_REQUEST',
                        f'New email: {new_email}')

        # Validaciones
        if not new_email or not confirm_email:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Ambos campos de email son requeridos.
            </div>
            '''

        if new_email != confirm_email:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Los emails no coinciden.
            </div>
            '''

        if new_email == user['email']:
            return '''
            <div class="alert alert-warning">
                <strong>Advertencia:</strong> El nuevo email es igual al actual.
            </div>
            '''

        # Validar formato de email
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, new_email):
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> El formato del email no es válido.
            </div>
            '''

        # Verificar que el nuevo email no esté en uso
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM users WHERE email = %s', (new_email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Este email ya está en uso por otra cuenta.
            </div>
            '''

        # Generar código de verificación
        verification_code = str(
            secrets.randbelow(900000) + 100000)  # 6 dígitos
        code_expires = datetime.now() + timedelta(minutes=10)

        # Guardar solicitud de cambio de email
        cursor.execute('''
            INSERT INTO email_change_requests (user_id, new_email, verification_code, expires)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET new_email = %s, verification_code = %s, expires = %s, created_at = CURRENT_TIMESTAMP
        ''', (user['id'], new_email, verification_code, code_expires, new_email, verification_code, code_expires))
        conn.commit()

        # Enviar email de verificación al NUEVO email
        from email_service import email_service
        if email_service.send_verification_code(new_email, user['name'], verification_code):
            log_user_action(
                user['id'], 'EMAIL_CHANGE_CODE_SENT', f'Code sent to: {new_email}')

            return f'''
            <div class="alert alert-success">
                <strong>✅ ¡Código enviado!</strong><br>
                Hemos enviado un código de verificación a <strong>{new_email}</strong>.<br>
                <button class="btn btn-primary btn-sm mt-2" 
                        hx-get="/profile/verify-email-change" 
                        hx-target="#email-change-alerts" 
                        hx-swap="innerHTML">
                    Verificar Código
                </button>
            </div>
            '''
        else:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> No se pudo enviar el email de verificación. Inténtalo de nuevo.
            </div>
            '''

    except Exception as e:
        log_error('request_email_change', e, f'User ID: {user["id"]}')
        return '''
        <div class="alert alert-danger">
            <strong>Error:</strong> No se pudo procesar la solicitud. Inténtalo de nuevo.
        </div>
        '''

@app.route('/profile/verify-email-change')
def verify_email_change_form():
    """Mostrar formulario de verificación de cambio de email"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'No autenticado'}), 401

    # Verificar que hay una solicitud pendiente
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT new_email, expires FROM email_change_requests 
        WHERE user_id = %s AND expires > %s
    ''', (user['id'], datetime.now()))
    request_data = cursor.fetchone()

    if not request_data:
        return '''
        <div class="alert alert-warning">
            <strong>Advertencia:</strong> No hay solicitudes de cambio de email pendientes o han expirado.
        </div>
        '''

    return f'''
    <div class="alert alert-info">
        <strong>📧 Verificando cambio a:</strong> {request_data[0]}
    </div>
    
    <form hx-post="/api/profile/verify-email-change" 
          hx-target="#email-change-alerts" 
          hx-swap="innerHTML"
          hx-indicator="#verify-loading">
      
      <div class="mb-3">
        <label for="verificationCode" class="form-label">Código de Verificación</label>
        <input type="text" class="form-control text-center" id="verificationCode" 
               name="verification_code" maxlength="6" placeholder="123456" required>
        <div class="form-text">Ingresa el código de 6 dígitos enviado a tu nuevo email</div>
      </div>
      
      <div class="d-grid gap-2">
        <button type="submit" class="btn btn-success">
          <span class="btn-text">✅ Confirmar Cambio de Email</span>
          <span id="verify-loading" class="spinner-border spinner-border-sm d-none" role="status"></span>
        </button>
        <button type="button" class="btn btn-outline-secondary" 
                hx-get="/profile/change-email" 
                hx-target="#security-modal" 
                hx-swap="innerHTML">
          ← Volver
        </button>
      </div>
    </form>
    '''

@app.route('/api/profile/verify-email-change', methods=['POST'])
@limiter.limit("10 per minute")
def confirm_email_change():
    """Confirmar cambio de email con código de verificación"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'No autenticado'}), 401

    try:
        data = request.form
        verification_code = data.get('verification_code', '').strip()

        if not verification_code:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> El código de verificación es requerido.
            </div>
            '''

        # Verificar código
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT new_email, verification_code, expires FROM email_change_requests 
            WHERE user_id = %s
        ''', (user['id'],))
        request_data = cursor.fetchone()

        if not request_data:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> No se encontró solicitud de cambio de email.
            </div>
            '''

        # Verificar que el código coincida
        if request_data[1] != verification_code:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Código de verificación incorrecto.
            </div>
            '''

        # Verificar que no haya expirado
        expires = request_data[2]
        if datetime.now() > expires:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> El código ha expirado. Solicita uno nuevo.
            </div>
            '''

        # Código válido - actualizar email
        old_email = user['email']
        new_email = request_data[0]

        cursor.execute('''
            UPDATE users 
            SET email = %s, updated_at = %s
            WHERE id = %s
        ''', (new_email, datetime.now(), user['id']))

        # Limpiar solicitud de cambio
        cursor.execute(
            'DELETE FROM email_change_requests WHERE user_id = %s', (user['id'],))

        conn.commit()

        log_user_action(user['id'], 'EMAIL_CHANGED_SUCCESS',
                        f'From: {old_email} To: {new_email}')
        log_database_operation(
            'UPDATE', 'users', f'Email changed for user {user["id"]}')

        return f'''
        <div class="alert alert-success">
            <strong>🎉 ¡Email cambiado exitosamente!</strong><br>
            Tu email ha sido actualizado de <strong>{old_email}</strong> a <strong>{new_email}</strong>.<br>
            <button type="button" class="btn btn-primary btn-sm mt-2" data-bs-dismiss="modal">
                Cerrar
            </button>
        </div>
        <script>
            // Recargar la página después de 3 segundos para mostrar el nuevo email
            setTimeout(function() {{
                window.location.reload();
            }}, 3000);
        </script>
        '''

    except Exception as e:
        log_error('confirm_email_change', e, f'User ID: {user["id"]}')
        return '''
        <div class="alert alert-danger">
            <strong>Error:</strong> No se pudo completar el cambio de email. Inténtalo de nuevo.
        </div>
        '''

@app.route('/api/profile/delete-account', methods=['POST'])
@limiter.limit("2 per minute")
@require_auth
def process_delete_account():
    """Procesar eliminación de cuenta"""
    user = get_current_user()

    try:
        data = request.form
        confirm_email = data.get('confirm_email', '').strip()
        confirm_delete = data.get('confirm_delete')

        log_user_action(user['id'], 'DELETE_ACCOUNT_ATTEMPT',
                        f'Email confirmation: {confirm_email}')

        # Validaciones de seguridad
        if not confirm_email:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Debes confirmar tu email.
            </div>
            '''

        if confirm_email != user['email']:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> El email no coincide. Debes escribir exactamente tu email actual.
            </div>
            '''

        if not confirm_delete:
            return '''
            <div class="alert alert-danger">
                <strong>Error:</strong> Debes marcar la casilla de confirmación.
            </div>
            '''

        # Proceder con la eliminación
        user_id = user['id']
        user_email = user['email']
        user_name = user['name']

        # 1. PRIMERO: Limpiar sesión actual inmediatamente
        session.clear()

        # 2. Log de cierre de sesión
        log_session_event(user_id, 'TERMINATED', 'Account deletion')

        conn = get_db()
        cursor = conn.cursor()

        # 3. Eliminar datos relacionados
        try:
            # Eliminar verificaciones de email pendientes
            cursor.execute(
                'DELETE FROM email_verification WHERE email = %s', (user_email,))
        except:
            pass  # Tabla no existe, continuar

        try:
            # Limpiar token de acceso del usuario
            cursor.execute('''
                UPDATE users 
                SET access_token = NULL, token_expires = NULL 
                WHERE id = %s
            ''', (user_id,))
        except:
            pass  # Error en update, continuar

        try:
            # Eliminar sesiones si la tabla existe
            cursor.execute('DELETE FROM sessions WHERE user_id = %s', (user_id,))
        except:
            pass  # Tabla no existe, continuar

        # 4. FINALMENTE: Eliminar el usuario
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))

        conn.commit()

        # Logging de eliminación exitosa
        log_user_action(user_id, 'ACCOUNT_DELETED_SUCCESS',
                        f'User: {user_name} ({user_email})')
        log_database_operation(
            'DELETE', 'users', f'Account deleted: ID {user_id}')

        return '''
        <div class="alert alert-success border-0 shadow-sm">
            <div class="d-flex align-items-center mb-3">
                <div class="me-3 fs-1">✅</div>
                <div>
                    <h5 class="alert-heading mb-1">Cuenta eliminada exitosamente</h5>
                    <p class="mb-0">Tu cuenta y todos los datos han sido eliminados permanentemente.</p>
                </div>
            </div>
            <hr>
            <div class="small">
                <p class="mb-2"><strong>✓ Sesión cerrada automáticamente</strong></p>
                <p class="mb-2"><strong>✓ Todos los datos eliminados</strong></p>
                <p class="mb-0"><strong>✓ Redirección al inicio en 3 segundos...</strong></p>
            </div>
        </div>
        <script>
            // Limpiar cualquier dato local del navegador
            if (typeof(Storage) !== "undefined") {
                localStorage.clear();
                sessionStorage.clear();
            }
            
            // Redirigir al inicio
            setTimeout(function() {
                window.location.href = '/';
            }, 3000);
        </script>
        '''

    except Exception as e:
        log_error('process_delete_account', e, f'User ID: {user["id"]}')
        # En modo debug, mostrar el error específico
        if app.debug:
            return f'''
            <div class="alert alert-danger">
                <strong>Error de Debug:</strong> {str(e)}
                <br><small>User ID: {user["id"]}</small>
            </div>
            '''
        return '''
        <div class="alert alert-danger">
            <strong>Error:</strong> No se pudo eliminar la cuenta. Inténtalo de nuevo o contacta soporte.
        </div>
        '''

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    try:
        user_id = session.get('user_id')
        log_user_action(user_id, 'LOGOUT_ATTEMPT', f'Method: {request.method}')

        # Limpiar token en base de datos
        if user_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET access_token = NULL, token_expires = NULL 
                WHERE id = %s
            ''', (user_id,))
            conn.commit()

            log_database_operation(
                'UPDATE', 'users', f'Cleared session for user {user_id}')

        # Limpiar sesión
        session.clear()
        log_user_action(user_id, 'LOGOUT_SUCCESS', 'Session cleared')

        # Si es una petición AJAX (POST), devolver JSON
        if request.method == 'POST':
            return jsonify({'success': True, 'redirect': url_for('index')})

        # Si es GET, redirigir normalmente
        return redirect(url_for('index'))

    except Exception as e:
        log_error('logout', e, f'User ID: {session.get("user_id")}')

        # En caso de error, limpiar sesión y redirigir
        session.clear()

        if request.method == 'POST':
            return jsonify({'success': True, 'redirect': url_for('index')})

        return redirect(url_for('index'))

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Endpoint de logout para HTMX"""
    try:
        user_id = session.get('user_id')
        log_user_action(user_id, 'LOGOUT_ATTEMPT', 'HTMX logout')

        # Limpiar token en base de datos
        if user_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET access_token = NULL, token_expires = NULL 
                WHERE id = %s
            ''', (user_id,))
            conn.commit()

            log_database_operation(
                'UPDATE', 'users', f'Cleared session for user {user_id}')

        # Limpiar sesión
        session.clear()
        log_user_action(user_id, 'LOGOUT_SUCCESS', 'HTMX session cleared')

        # Logout elegante - Redirigir manteniendo SPA
        logout_location = {
            "path": url_for('index'),
            "target": "body",
            "swap": "innerHTML"
        }

        return '', 200, {'HX-Location': json.dumps(logout_location)}

    except Exception as e:
        log_error('api_logout', e, f'User ID: {session.get("user_id")}')
        session.clear()

        # En caso de error, también logout elegante
        logout_location = {
            "path": url_for('index'),
            "target": "body",
            "swap": "innerHTML"
        }

        return '', 200, {'HX-Location': json.dumps(logout_location)}

@app.route('/api/session-status')
def session_status():
    """Endpoint para verificar estado de sesión"""
    user = get_current_user()
    if not user:
        return '<span id="session-time-remaining" class="text-danger">No autenticado</span>'

    # Calcular tiempo restante de sesión
    if user['token_expires']:
        expires = datetime.fromisoformat(user['token_expires'])
        time_left = expires - datetime.now()
        total_minutes = int(time_left.total_seconds() / 60)

        if total_minutes <= 0:
            session_time_info = {
                'minutes_remaining': 0,
                'hours_remaining': 0,
                'mins_remaining': 0,
                'is_expiring_soon': True
            }
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60

            session_time_info = {
                'minutes_remaining': total_minutes,
                'hours_remaining': hours,
                'mins_remaining': minutes,
                'is_expiring_soon': total_minutes < 30
            }

        session_info = {
            'expires_at': user['token_expires'][:19] if user['token_expires'] else 'No definido',
            **session_time_info
        }

        return render_template('session_status.html', session_info=session_info)

    return '<span id="session-time-remaining" class="text-danger">Sesión sin expiración definida</span>'

@app.route('/api/session-warning')
def session_warning():
    """Endpoint para avisos de sesión próxima a expirar"""
    user = get_current_user()
    if not user:
        return '', 204

    # Verificar si la sesión está próxima a expirar (10 minutos antes de expirar)
    if user['token_expires']:
        # PostgreSQL returns datetime objects directly, unlike SQLite which returns strings
        if isinstance(user['token_expires'], str):
            expires = datetime.fromisoformat(user['token_expires'])
        else:
            expires = user['token_expires']
            
        time_left = expires - datetime.now()
        total_minutes = int(time_left.total_seconds() / 60)

        if total_minutes <= 10 and total_minutes > 0:
            return render_template('session_warning_modal.html',
                                   time_remaining=f"{total_minutes} minutos")

    return '', 204

@app.route('/api/extend-session', methods=['POST'])
@limiter.limit("5 per minute")
@require_auth
def extend_session():
    """Extender la sesión del usuario por 2 horas más"""
    user = get_current_user()

    try:
        # Extender la sesión por 8 horas más
        new_expires = datetime.now() + timedelta(hours=8)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET token_expires = %s, updated_at = %s
            WHERE id = %s
        ''', (new_expires, datetime.now(), user['id']))
        conn.commit()

        log_user_action(user['id'], 'EXTEND_SESSION',
                        f'Session extended until {new_expires}')
        log_database_operation(
            'UPDATE', 'users', f'Session extended for user {user["id"]}')

        return jsonify({
            'success': True,
            'message': 'Sesión extendida exitosamente',
            'new_expires': new_expires.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        log_error('extend_session', e, f'User ID: {user["id"]}')
        return jsonify({
            'error': True,
            'message': 'Error al extender la sesión'
        }), 500

@app.route('/api/session-info')
def session_info():
    """Endpoint para información detallada de sesión"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'No authenticated'}), 401

    # Preparar información de sesión
    if user['token_expires']:
        # PostgreSQL returns datetime objects directly, unlike SQLite which returns strings
        if isinstance(user['token_expires'], str):
            expires = datetime.fromisoformat(user['token_expires'])
        else:
            expires = user['token_expires']
            
        time_left = expires - datetime.now()
        total_minutes = int(time_left.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        session_data = {
            'authenticated': True,
            'user_id': user['id'],
            'expires_at': user['token_expires'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(user['token_expires'], datetime) else user['token_expires'][:19],
            'minutes_remaining': max(0, total_minutes),
            'hours_remaining': max(0, hours),
            'mins_remaining': max(0, minutes),
            'is_expiring_soon': total_minutes < 30
        }
    else:
        session_data = {
            'authenticated': True,
            'user_id': user['id'],
            'expires_at': 'No definido',
            'minutes_remaining': 0,
            'hours_remaining': 0,
            'mins_remaining': 0,
            'is_expiring_soon': True
        }

    return jsonify(session_data)

@app.route('/api/auth/register', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def auth_register():
    """Endpoint para registro de nuevos usuarios"""
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()

        log_request('/api/auth/register', 'POST',
                    {'name': name, 'email': email})

        if not name or not email:
            return jsonify({
                'error': True,
                'code': 'MISSING_FIELDS',
                'message': 'Nombre y email son requeridos'
            }), 400

        # Validar formato de email básico
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'error': True,
                'code': 'INVALID_EMAIL_FORMAT',
                'message': 'El formato del email no es válido'
            }), 400

        # Verificar que el email no exista
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({
                'error': True,
                'code': 'EMAIL_ALREADY_EXISTS',
                'message': 'Este email ya está registrado',
                'suggestion': 'login'
            }), 409

        # Generar código de verificación
        verification_code = str(
            secrets.randbelow(900000) + 100000)  # 6 dígitos
        code_expires = datetime.now() + timedelta(minutes=10)

        # Guardar código temporal
        cursor.execute('''
            INSERT INTO email_verification (email, name, code, expires)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) 
            DO UPDATE SET name = %s, code = %s, expires = %s, created_at = CURRENT_TIMESTAMP
        ''', (email, name, verification_code, code_expires, name, verification_code, code_expires))
        conn.commit()

        # Enviar email con código
        from email_service import email_service
        if email_service.send_verification_code(email, name, verification_code):
            log_response('/api/auth/register', 200,
                         'Código enviado exitosamente')
            return jsonify({
                'success': True,
                'message': 'Código de verificación enviado a tu email',
                'action': 'verify_email',
                'email': email,
                'name': name
            })
        else:
            log_response('/api/auth/register', 503, 'Error enviando email')
            return jsonify({
                'error': True,
                'code': 'EMAIL_SEND_ERROR',
                'message': 'Error enviando email. Verifica tu configuración SMTP'
            }), 503

    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        log_error('auth_register', e, traceback_str)
        log_response('/api/auth/register', 500, 'Error interno del servidor')
        return jsonify({
            'error': True,
            'code': 'SERVER_ERROR',
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def auth_login():
    """Endpoint para login de usuarios existentes"""
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip()

        if not email:
            return jsonify({
                'error': True,
                'code': 'MISSING_EMAIL',
                'message': 'Email es requerido'
            }), 400

        # Verificar que el email existe
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if not existing_user:
            return jsonify({
                'error': True,
                'code': 'EMAIL_NOT_FOUND',
                'message': 'Email no encontrado',
                'suggestion': 'register'
            }), 404

        # Generar código de verificación
        verification_code = str(secrets.randbelow(900000) + 100000)
        code_expires = datetime.now() + timedelta(minutes=10)

        # Guardar código temporal
        cursor.execute('''
            INSERT INTO email_verification (email, name, code, expires)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) 
            DO UPDATE SET name = %s, code = %s, expires = %s, created_at = CURRENT_TIMESTAMP
        ''', (email, existing_user[1], verification_code, code_expires, existing_user[1], verification_code, code_expires))
        conn.commit()

        # Enviar email con código
        from email_service import email_service
        email_sent = email_service.send_verification_code(
            email, existing_user[1], verification_code)

        if email_sent:
            return jsonify({
                'success': True,
                'message': 'Código de verificación enviado a tu email',
                'action': 'verify_email',
                'email': email,
                'name': existing_user[1]
            })
        else:
            # MODO DESARROLLO - Mostrar código en logs para poder continuar
            if app.debug:
                app_logger.warning(
                    f"🧪 MODO DEBUG - Email falló, código para desarrollo:")
                app_logger.warning(f"📧 Email: {email}")
                app_logger.warning(f"👤 Nombre: {existing_user[1]}")
                app_logger.warning(f"🔢 CÓDIGO: {verification_code}")

                return jsonify({
                    'success': True,
                    'message': f'⚠️ MODO DEBUG: Email falló. Código: {verification_code}',
                    'action': 'verify_email',
                    'email': email,
                    'name': existing_user[1],
                    'debug_code': verification_code  # Solo en modo debug
                })
            else:
                return jsonify({
                    'error': True,
                    'code': 'EMAIL_SEND_ERROR',
                    'message': 'Error enviando email'
                }), 503

    except Exception as e:
        import traceback
        log_error('auth_login', e, traceback.format_exc())
        return jsonify({
            'error': True,
            'code': 'SERVER_ERROR',
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/auth/verify-email', methods=['POST'])
@csrf.exempt
@limiter.limit("15 per minute")
def auth_verify_email():
    """Endpoint para verificar código de email"""
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip()
        code = data.get('code', '').strip()
        action = data.get('action', '').strip()  # 'login' o 'register'

        if not email or not code:
            return jsonify({
                'error': True,
                'code': 'MISSING_FIELDS',
                'message': 'Email y código son requeridos'
            }), 400

        # Verificar código de email
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, code, expires FROM email_verification 
            WHERE email = %s
        ''', (email,))
        verification = cursor.fetchone()

        if not verification:
            return jsonify({
                'error': True,
                'code': 'VERIFICATION_NOT_FOUND',
                'message': 'No se encontró verificación para este email'
            }), 404

        # Verificar que el código coincida
        if verification[1] != code:
            return jsonify({
                'error': True,
                'code': 'INVALID_CODE',
                'message': 'Código de verificación incorrecto'
            }), 400

        # Verificar que no haya expirado
        expires = verification[2]
        if datetime.now() > expires:
            return jsonify({
                'error': True,
                'code': 'CODE_EXPIRED',
                'message': 'El código ha expirado'
            }), 400

        # Limpiar verificación usada
        cursor.execute(
            'DELETE FROM email_verification WHERE email = %s', (email,))
        conn.commit()

        # Si es registro, crear usuario
        if action == 'register':
            name = verification[0]
            user_id = create_user_email(name, email)
            if not user_id:
                return jsonify({
                    'error': True,
                    'code': 'USER_CREATION_ERROR',
                    'message': 'Error creando usuario'
                }), 500
        else:
            # Si es login, obtener usuario existente
            cursor.execute(
                'SELECT id FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()

            if not user:
                return jsonify({
                    'error': True,
                    'code': 'USER_NOT_FOUND',
                    'message': 'Usuario no encontrado'
                }), 404

            user_id = user[0]

        # Crear sesión
        access_token = create_user_session_email(user_id)
        if not access_token:
            return jsonify({
                'error': True,
                'code': 'SESSION_ERROR',
                'message': 'Error creando sesión'
            }), 500

        # Configurar sesión Flask
        session.permanent = True
        session['user_id'] = user_id
        session['access_token'] = access_token

        # Obtener datos del usuario para respuesta
        user = get_current_user()
        log_user_action(user_id, 'LOGIN_SUCCESS', f'Email: {email}')

        return jsonify({
            'success': True,
            'message': 'Autenticación exitosa',
            'user': {
                'id': user['id'],
                'name': get_user_display_name(user),
                'email': user['email'] if user['email'] else email
            },
            'token': access_token
        })

    except Exception as e:
        import traceback
        log_error('auth_verify_email', e, traceback.format_exc())
        return jsonify({
            'error': True,
            'code': 'SERVER_ERROR',
            'message': 'Error interno del servidor'
        }), 500

@app.route('/admin/test-smtp')
@require_debug
def test_smtp():
    """Probar configuración SMTP"""
    from email_service import email_service

    # Probar envío de email de prueba
    test_email = "ecabrerablazquez@gmail.com"  # Tu email
    test_result = email_service.send_verification_code(
        test_email,
        "Usuario de Prueba",
        "123456"
    )

    if test_result:
        return f"""
        <h2>✅ SMTP Configurado Correctamente</h2>
        <p>Email de prueba enviado exitosamente a: {test_email}</p>
        <p>Revisa tu bandeja de entrada.</p>
        <a href="/admin/logs">Ver logs</a>
        """
    else:
        return f"""
        <h2>❌ Error en Configuración SMTP</h2>
        <p>No se pudo enviar email de prueba a: {test_email}</p>
        <p>Revisa los logs para más detalles.</p>
        <a href="/admin/logs">Ver logs de error</a>
        """

@app.route('/api/borrar-fotos', methods=['POST'])
@require_auth
def borrar_fotos():
    """API para borrar fotos seleccionadas"""
    try:
        user = get_current_user()
        data = request.get_json()
        foto_ids = data.get('foto_ids', [])

        if not foto_ids:
            return jsonify({'success': False, 'message': 'No se proporcionaron IDs de fotos'}), 400

        conn = get_db()
        cursor = conn.cursor()
        deleted_count = 0

        # Verificar que las fotos pertenecen al usuario actual y borrarlas
        for foto_id in foto_ids:
            # Verificar propiedad y obtener info de la foto
            cursor.execute('''
                SELECT nombre_archivo FROM photos 
                WHERE id = %s AND user_id = %s
            ''', (foto_id, user['id']))
            foto = cursor.fetchone()

            if foto:
                # Extraer public_id de la URL de Cloudinary y borrar
                cloudinary_url = foto[0]
                try:
                    # URL típica: https://res.cloudinary.com/dquxfl0fe/image/upload/v1234567890/familia/photo_20250813_abc123.jpg
                    # Extraer: familia/photo_20250813_abc123
                    parts = cloudinary_url.split('/')
                    if 'familia' in parts:
                        familia_index = parts.index('familia')
                        public_id_with_extension = '/'.join(
                            parts[familia_index:])
                        # Quitar extensión (.jpg, .png, etc.)
                        public_id = public_id_with_extension.rsplit('.', 1)[0]

                        # Borrar de Cloudinary
                        result = cloudinary.uploader.destroy(public_id)
                        print(
                            f"✅ Cloudinary delete result for {public_id}: {result}")

                except Exception as e:
                    print(f"❌ Error borrando de Cloudinary: {e}")
                    # Continuar aunque falle Cloudinary

                # Borrar de base de datos
                cursor.execute(
                    'DELETE FROM photos WHERE id = %s AND user_id = %s', (foto_id, user['id']))
                deleted_count += 1

        conn.commit()

        log_user_action(user['id'], 'DELETE_PHOTOS',
                        f'Deleted {deleted_count} photos')

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} foto{"s" if deleted_count != 1 else ""} borrada{"s" if deleted_count != 1 else ""} correctamente'
        })

    except Exception as e:
        log_error('borrar_fotos', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@app.route('/ver-mis-fotos')
@require_auth
def ver_mis_fotos():
    """Mostrar solo las fotos del usuario actual ordenadas por año y mes"""
    try:
        user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Obtener solo las fotos del usuario actual ordenadas por año DESC, mes DESC
        cursor.execute('''
            SELECT p.*, u.name as usuario_nombre
            FROM photos p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = %s
            ORDER BY p.año DESC, p.mes DESC, p.created_at DESC
        ''', (user['id'],))
        fotos = cursor.fetchall()

        # Convertir a lista de diccionarios para facilitar el manejo en el template
        fotos_list = []
        columns = [desc[0] for desc in cursor.description]
        for foto in fotos:
            foto_dict = dict(zip(columns, foto))
            # Determinar si necesita etiquetado
            personas_ids = foto_dict['personas_ids']
            necesita_etiquetado = (
                not personas_ids or
                personas_ids == 'null' or
                personas_ids == '' or
                personas_ids == '[]' or
                personas_ids == 'None'
            )

            fotos_list.append({
                'id': foto_dict['id'],
                'nombre': foto_dict['nombre'],
                'nombre_archivo': foto_dict['nombre_archivo'],  # URL de Cloudinary
                'mes': foto_dict['mes'],
                'año': foto_dict['año'],
                'usuario_nombre': foto_dict['usuario_nombre'],
                'created_at': foto_dict['created_at'],
                'personas_ids': foto_dict['personas_ids'],
                'necesita_etiquetado': necesita_etiquetado
            })

        log_user_action(user['id'], 'VIEW_MY_PHOTOS',
                        f'Viewed {len(fotos_list)} own photos')

        return render_template('galeria_mis_fotos.html', fotos=fotos_list, user=user)

    except Exception as e:
        log_error('ver_mis_fotos', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return render_template('error.html', message='Error al cargar las fotos'), 500

@app.route('/gestionar-personas')
@require_auth
def gestionar_personas():
    """Mostrar página para gestionar personas"""
    user = None
    try:
        user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Obtener todas las personas
        cursor.execute('''
            SELECT id, nombre, imagen, created_at
            FROM personas
            ORDER BY nombre ASC
        ''')
        personas = cursor.fetchall()

        # Convertir a lista de diccionarios
        personas_list = []
        columns = [desc[0] for desc in cursor.description]
        for persona in personas:
            persona_dict = dict(zip(columns, persona))
            # Convertir datetime a string para compatibilidad con la plantilla
            created_at = persona_dict['created_at']
            if hasattr(created_at, 'strftime'):
                # Es un objeto datetime (PostgreSQL), convertir a string
                persona_dict['created_at'] = created_at.strftime('%Y-%m-%d %H:%M:%S')
            
            personas_list.append({
                'id': persona_dict['id'],
                'nombre': persona_dict['nombre'],
                'imagen': persona_dict['imagen'],
                'created_at': persona_dict['created_at']
            })

        if user:
            log_user_action(user['id'], 'VIEW_PERSONS',
                            f'Viewed {len(personas_list)} persons')

        return render_template('gestionar_personas.html', personas=personas_list, user=user)

    except Exception as e:
        user_id = user['id'] if user else "Unknown"
        log_error('gestionar_personas', e, f'User: {user_id}')
        return render_template('error.html', message='Error al cargar las personas'), 500

@app.route('/ver-todas-fotos')
@require_auth
def ver_todas_fotos():
    """Mostrar todas las fotos ordenadas por año y mes"""
    try:
        user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Obtener todas las fotos ordenadas por año DESC, mes DESC (más recientes primero)
        cursor.execute('''
            SELECT p.*, u.name as usuario_nombre
            FROM photos p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.año DESC, p.mes DESC, p.created_at DESC
        ''')
        fotos = cursor.fetchall()

        # Convertir a lista de diccionarios para facilitar el manejo en el template
        fotos_list = []
        columns = [desc[0] for desc in cursor.description]
        for foto in fotos:
            foto_dict = dict(zip(columns, foto))
            # Determinar si necesita etiquetado
            personas_ids = foto_dict['personas_ids']
            necesita_etiquetado = (
                not personas_ids or
                personas_ids == 'null' or
                personas_ids == '' or
                personas_ids == '[]' or
                personas_ids == 'None'
            )

            fotos_list.append({
                'id': foto_dict['id'],
                'nombre': foto_dict['nombre'],
                'nombre_archivo': foto_dict['nombre_archivo'],  # URL de Cloudinary
                'mes': foto_dict['mes'],
                'año': foto_dict['año'],
                'usuario_nombre': foto_dict['usuario_nombre'],
                'created_at': foto_dict['created_at'],
                'personas_ids': foto_dict['personas_ids'],
                'necesita_etiquetado': necesita_etiquetado
            })

        log_user_action(user['id'], 'VIEW_ALL_PHOTOS',
                        f'Viewed {len(fotos_list)} photos')

        return render_template('galeria_todas_fotos.html',
                               fotos=fotos_list,
                               user=user)

    except Exception as e:
        log_error('ver_todas_fotos', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return render_template('error.html', message='Error al cargar las fotos'), 500

@app.route('/api/get-personas', methods=['GET'])
@require_auth
def get_personas():
    """Obtener lista de personas para filtros"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nombre
            FROM personas
            ORDER BY nombre ASC
        ''')
        personas = cursor.fetchall()

        personas_list = []
        for persona in personas:
            personas_list.append({
                'id': persona[0],
                'nombre': persona[1]
            })

        return jsonify({
            'success': True,
            'personas': personas_list
        })

    except Exception as e:
        log_error('get_personas', e, 'Error getting personas list')
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@app.route('/api/upload-person-image', methods=['POST'])
@require_auth
def upload_person_image():
    """Subir imagen de persona a Cloudinary"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No se proporcionó archivo'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No se seleccionó archivo'}), 400

        # Subir a Cloudinary en carpeta personas
        result = cloudinary.uploader.upload(
            file,
            folder="personas",
            resource_type="image",
            format="jpg",
            quality="auto:good",
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto:good"}
            ]
        )

        return jsonify({
            'success': True,
            'url': result['secure_url'],
            'public_id': result['public_id']
        })

    except Exception as e:
        user = get_current_user()
        log_error('upload_person_image', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'success': False, 'message': 'Error subiendo imagen'}), 500

@app.route('/api/add-person', methods=['POST'])
@require_auth
def add_person():
    """Agregar nueva persona o editar existente"""
    try:
        data = request.get_json()
        person_id = data.get('id')
        nombre = data.get('nombre', '').strip()
        imagen_url = data.get('imagen_url', '').strip()

        if not nombre:
            return jsonify({'success': False, 'message': 'El nombre es requerido'}), 400

        conn = get_db()
        cursor = conn.cursor()
        user = get_current_user()

        # Si hay ID, es una edición
        if person_id:
            # Verificar que la persona existe
            cursor.execute(
                'SELECT id, nombre FROM personas WHERE id = %s', (person_id,))
            existing = cursor.fetchone()
            if not existing:
                return jsonify({'success': False, 'message': 'Persona no encontrada'}), 404

            # Verificar que no existe otra persona con el mismo nombre
            cursor.execute(
                'SELECT id FROM personas WHERE nombre = %s AND id != %s', (nombre, person_id))
            name_conflict = cursor.fetchone()
            if name_conflict:
                return jsonify({'success': False, 'message': 'Ya existe otra persona con ese nombre'}), 400

            # Actualizar persona existente
            cursor.execute('''
                UPDATE personas 
                SET nombre = %s, imagen = %s, updated_at = %s
                WHERE id = %s
            ''', (nombre, imagen_url, datetime.now(), person_id))

            conn.commit()

            log_user_action(user['id'], 'EDIT_PERSON',
                            f'Edited person: {nombre}')

            return jsonify({
                'success': True,
                'person_id': person_id,
                'message': f'Persona "{nombre}" actualizada correctamente'
            })

        else:
            # Es una nueva persona
            # Verificar que no existe una persona con el mismo nombre
            cursor.execute(
                'SELECT id FROM personas WHERE nombre = %s', (nombre,))
            existing = cursor.fetchone()
            if existing:
                return jsonify({'success': False, 'message': 'Ya existe una persona con ese nombre'}), 400

            # Insertar nueva persona
            cursor.execute('''
                INSERT INTO personas (nombre, imagen, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (nombre, imagen_url, datetime.now(), datetime.now()))

            person_id = cursor.fetchone()[0]
            conn.commit()

            log_user_action(user['id'], 'ADD_PERSON',
                            f'Added person: {nombre}')

            return jsonify({
                'success': True,
                'person_id': person_id,
                'message': f'Persona "{nombre}" agregada correctamente'
            })

    except Exception as e:
        log_error('add_person', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@app.route('/api/get-all-persons')
@require_auth
def get_all_persons():
    """Obtener todas las personas para el buscador"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nombre FROM personas 
            ORDER BY nombre
        ''')
        personas = cursor.fetchall()

        return jsonify({
            'success': True,
            'persons': [{'id': p[0], 'nombre': p[1]} for p in personas]
        })

    except Exception as e:
        return jsonify({'success': False, 'message': 'Error obteniendo personas'}), 500

@app.route('/api/buscar-fotos-persona')
@require_auth
def buscar_fotos_persona():
    """Buscar fotos por nombre de persona"""
    try:
        user = get_current_user()
        buscar_persona = request.args.get('buscar_persona', '').strip()

        conn = get_db()
        cursor = conn.cursor()

        if not buscar_persona:
            # Mostrar todas las fotos
            cursor.execute('''
                SELECT p.id, p.nombre, p.nombre_archivo, p.mes, p.año, p.created_at, p.personas_ids,
                       u.name as usuario_nombre
                FROM photos p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.created_at DESC
            ''')
            fotos = cursor.fetchall()
        else:
            # Buscar en todas las fotos
            cursor.execute('''
                SELECT p.id, p.nombre, p.nombre_archivo, p.mes, p.año, p.created_at, p.personas_ids,
                       u.name as usuario_nombre
                FROM photos p
                JOIN users u ON p.user_id = u.id
                ORDER BY p.created_at DESC
            ''')
            fotos = cursor.fetchall()

            # Filtrar por nombre de foto O por persona
            fotos_filtradas = []
            columns = [desc[0] for desc in cursor.description]
            for foto in fotos:
                foto_dict = dict(zip(columns, foto))
                # Buscar en el nombre de la foto
                if buscar_persona.lower() in foto_dict['nombre'].lower():
                    fotos_filtradas.append(foto_dict)
                    continue

                # Buscar en las personas de la foto
                try:
                    import json
                    personas_ids = json.loads(
                        foto_dict['personas_ids']) if foto_dict['personas_ids'] else []
                    if personas_ids:
                        placeholders = ','.join(['%s' for _ in personas_ids])
                        cursor.execute(f'''
                            SELECT nombre FROM personas 
                            WHERE id IN ({placeholders})
                        ''', personas_ids)
                        personas = cursor.fetchall()

                        for persona in personas:
                            if buscar_persona.lower() in persona[0].lower():
                                fotos_filtradas.append(foto_dict)
                                break
                except:
                    continue

            fotos = fotos_filtradas

        # Agregar información de si necesita etiquetado
        fotos_con_info = []
        for foto in fotos:
            if isinstance(foto, dict):
                foto_dict = foto
            else:
                columns = [desc[0] for desc in cursor.description]
                foto_dict = dict(zip(columns, foto))
            
            # Determinar si necesita etiquetado
            personas_ids = foto_dict['personas_ids']
            necesita_etiquetado = (
                not personas_ids or
                personas_ids == 'null' or
                personas_ids == '' or
                personas_ids == '[]' or
                personas_ids == 'None'
            )
            foto_dict['necesita_etiquetado'] = necesita_etiquetado
            fotos_con_info.append(foto_dict)

        # Renderizar template completo de galería con fotos filtradas
        return render_template('galeria_todas_fotos.html', fotos=fotos_con_info, user=user)

    except Exception as e:
        return f"<div class='alert alert-danger'>Error: {str(e)}</div>"

@app.route('/api/buscar-mis-fotos-persona')
def buscar_mis_fotos_persona():
    """Buscar mis fotos por nombre de persona"""
    try:
        user = get_current_user()
        buscar_persona = request.args.get('buscar_persona', '').strip()

        conn = get_db()
        cursor = conn.cursor()

        if not buscar_persona:
            # Si no hay búsqueda, mostrar todas mis fotos
            cursor.execute('''
                SELECT id, nombre, nombre_archivo, mes, año, created_at, personas_ids
                FROM photos 
                WHERE user_id = %s
                ORDER BY created_at DESC
            ''', (user['id'],))
            fotos = cursor.fetchall()
        else:
            # Buscar en todas mis fotos
            cursor.execute('''
                SELECT id, nombre, nombre_archivo, mes, año, created_at, personas_ids
                FROM photos 
                WHERE user_id = %s
                ORDER BY created_at DESC
            ''', (user['id'],))
            fotos = cursor.fetchall()

            # Filtrar por nombre de foto O por persona
            fotos_filtradas = []
            columns = [desc[0] for desc in cursor.description]
            for foto in fotos:
                foto_dict = dict(zip(columns, foto))
                # Buscar en el nombre de la foto
                if buscar_persona.lower() in foto_dict['nombre'].lower():
                    fotos_filtradas.append(foto_dict)
                    continue

                # Buscar en las personas de la foto
                try:
                    import json
                    personas_ids = json.loads(
                        foto_dict['personas_ids']) if foto_dict['personas_ids'] else []
                    if personas_ids:
                        placeholders = ','.join(['%s' for _ in personas_ids])
                        cursor.execute(f'''
                            SELECT nombre FROM personas 
                            WHERE id IN ({placeholders})
                        ''', personas_ids)
                        personas = cursor.fetchall()

                        for persona in personas:
                            if buscar_persona.lower() in persona[0].lower():
                                fotos_filtradas.append(foto_dict)
                                break
                except:
                    continue

            fotos = fotos_filtradas

        # Agregar información de si necesita etiquetado
        fotos_con_info = []
        for foto in fotos:
            if isinstance(foto, dict):
                foto_dict = foto
            else:
                columns = [desc[0] for desc in cursor.description]
                foto_dict = dict(zip(columns, foto))
            
            # Determinar si necesita etiquetado
            personas_ids = foto_dict['personas_ids']
            necesita_etiquetado = (
                not personas_ids or
                personas_ids == 'null' or
                personas_ids == '' or
                personas_ids == '[]' or
                personas_ids == 'None'
            )
            foto_dict['necesita_etiquetado'] = necesita_etiquetado
            fotos_con_info.append(foto_dict)

        # Renderizar template completo de mis fotos con fotos filtradas
        return render_template('galeria_mis_fotos.html', fotos=fotos_con_info, user=user)

    except Exception as e:
        return f"<div class='alert alert-danger'>Error buscando fotos: {str(e)}</div>"

@app.route('/api/test-buscar-fotos')
def test_buscar_fotos():
    """Endpoint de prueba para búsqueda"""
    buscar_persona = request.args.get('buscar_persona', '')

    if not buscar_persona:
        return "<div class='alert alert-info'>Escribe algo para buscar</div>"

    return f"""
    <div class="col-12">
        <div class="alert alert-success">
            <h5>Buscando: {buscar_persona}</h5>
            <p>Endpoint funcionando correctamente</p>
        </div>
    </div>
    """

@app.route('/api/delete-person', methods=['POST'])
@require_auth
def delete_person():
    """Eliminar persona"""
    try:
        data = request.get_json()
        person_id = data.get('person_id')

        if not person_id:
            return jsonify({'success': False, 'message': 'ID de persona requerido'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Obtener info de la persona antes de borrar
        cursor.execute(
            'SELECT nombre, imagen FROM personas WHERE id = %s', (person_id,))
        persona = cursor.fetchone()
        if not persona:
            return jsonify({'success': False, 'message': 'Persona no encontrada'}), 404

        # Eliminar de Cloudinary si tiene imagen
        if persona[1]:
            try:
                # Extraer public_id y eliminar de Cloudinary
                parts = persona[1].split('/')
                if 'familia' in parts:
                    familia_index = parts.index('familia')
                    public_id_with_extension = '/'.join(parts[familia_index:])
                    public_id = public_id_with_extension.rsplit('.', 1)[0]
                    cloudinary.uploader.destroy(public_id)
            except Exception as e:
                print(
                    f"❌ Error eliminando imagen de persona de Cloudinary: {e}")

        # Eliminar persona
        cursor.execute('DELETE FROM personas WHERE id = %s', (person_id,))
        conn.commit()

        user = get_current_user()
        log_user_action(user['id'], 'DELETE_PERSON',
                        f'Deleted person: {persona[0]}')

        return jsonify({
            'success': True,
            'message': f'Persona "{persona[0]}" eliminada correctamente'
        })

    except Exception as e:
        user = get_current_user()
        log_error('delete_person', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@app.route('/procesando-reconocimiento')
@require_auth
def procesando_reconocimiento():
    """Mostrar pantalla de procesamiento de reconocimiento facial"""
    user = get_current_user()
    foto_ids = request.args.get('ids', '')
    log_user_action(user['id'], 'VIEW_PROCESSING_FACIAL',
                    f'Viewing facial recognition processing for photos: {foto_ids}')
    return render_template('procesando_reconocimiento.html', user=user)

@app.route('/api/procesar-reconocimiento-facial')
@require_auth
def api_procesar_reconocimiento_facial():
    """API para procesar reconocimiento facial de fotos recientes"""
    start_time = time.time()  # Medir tiempo de procesamiento
    try:
        user = get_current_user()
        conn = get_db()
        cursor = conn.cursor()

        # Obtener IDs de fotos específicas desde la query string
        ids_param = request.args.get('ids', '')
        print(f"IDs recibidos: '{ids_param}'")

        foto_ids = ids_param.split(',')
        foto_ids = [id.strip() for id in foto_ids if id.strip().isdigit()]

        if not foto_ids:
            return render_template('etiquetar_caras_individuales.html', caras=[], user=user)

        # Obtener fotos con información de personas
        placeholders = ','.join(['%s' for _ in foto_ids])
        cursor.execute(f'''
            SELECT id, nombre, nombre_archivo, mes, año, created_at, personas_ids
            FROM photos 
            WHERE id IN ({placeholders}) AND user_id = %s
            ORDER BY created_at DESC
        ''', foto_ids + [user['id']])
        fotos_recientes = cursor.fetchall()

        print(f"Fotos encontradas: {len(fotos_recientes)}")

        # Verificar si se fuerza el reprocesamiento
        force_reprocess = request.args.get('force', '').lower() == 'true'

        # Separar fotos que ya tienen personas identificadas vs las que no
        fotos_ya_procesadas = []
        fotos_sin_procesar = []

        columns = [desc[0] for desc in cursor.description]
        for foto in fotos_recientes:
            foto_dict = dict(zip(columns, foto))
            if foto_dict['personas_ids'] and foto_dict['personas_ids'].strip() and foto_dict['personas_ids'] != 'null' and not force_reprocess:
                fotos_ya_procesadas.append(foto_dict)
                print(
                    f"Foto {foto_dict['id']} ya tiene personas: {foto_dict['personas_ids']}")
            else:
                fotos_sin_procesar.append(foto_dict)
                if force_reprocess:
                    print(f"Foto {foto_dict['id']} será reprocesada (force=true)")
                else:
                    print(f"Foto {foto_dict['id']} sin procesar")

        # Si todas las fotos ya están procesadas y no se fuerza reprocesamiento, mostrar resumen
        if len(fotos_ya_procesadas) > 0 and len(fotos_sin_procesar) == 0 and not force_reprocess:
            print("Todas las fotos ya están procesadas, mostrando resumen")
            return mostrar_resumen_fotos_procesadas(fotos_ya_procesadas, user, conn)

        # Si hay mezcla, procesar solo las que faltan pero mostrar aviso
        if len(fotos_ya_procesadas) > 0 and not force_reprocess:
            print(
                f"Hay {len(fotos_ya_procesadas)} fotos ya procesadas y {len(fotos_sin_procesar)} sin procesar")

        # Procesar las fotos correspondientes
        fotos_a_procesar = fotos_sin_procesar if not force_reprocess else [dict(zip(columns, foto)) for foto in fotos_recientes]

        caras_individuales = []

        # Procesar fotos en paralelo para mejor rendimiento
        def procesar_foto_individual(foto):
            """Procesa una foto individual y retorna las caras encontradas"""
            caras_foto = []
            print(f"Procesando foto: {foto['nombre']}")

            try:
                faces = detect_faces_facepp(foto['nombre_archivo'])

                if faces:
                    print(
                        f"Face++ detectó {len(faces)} caras en {foto['nombre']}")

                    # Procesar cada cara de esta foto
                    for idx, cara in enumerate(faces):
                        try:
                            face_rectangle = cara['face_rectangle']
                            buffer = get_face_crop(
                                foto['nombre_archivo'], face_rectangle)

                            if not buffer:
                                print(
                                    f"Error creando recorte para cara {idx + 1} de {foto['nombre']}")
                                continue

                            # Subir a Cloudinary
                            upload_result = upload_temp_face_crop(buffer)

                            if upload_result.get('secure_url'):
                                caras_foto.append({
                                    'foto_id': foto['id'],
                                    'foto_nombre': foto['nombre'],
                                    'cara_index': idx,
                                    'face_token': cara['face_token'],
                                    'recorte_url': upload_result['secure_url'],
                                    'recorte_public_id': upload_result['public_id'],
                                    'cara_id': f"{foto['id']}_{idx}"
                                })
                                print(
                                    f"Cara {idx + 1} de {foto['nombre']} procesada exitosamente")

                        except Exception as e:
                            print(
                                f"Error procesando cara {idx + 1} de {foto['nombre']}: {e}")
                            continue
                else:
                    print(f"No se detectaron caras en {foto['nombre']}")

            except Exception as e:
                print(f"Error con Face++ para {foto['nombre']}: {e}")

            return caras_foto

        # Procesar fotos en paralelo (máximo 3 threads para no sobrecargar APIs)
        max_workers = min(3, len(fotos_a_procesar))
        print(
            f"Procesando {len(fotos_a_procesar)} fotos con {max_workers} threads paralelos")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las fotos para procesamiento paralelo
            future_to_foto = {executor.submit(
                procesar_foto_individual, foto): foto for foto in fotos_a_procesar}

            # Recopilar resultados conforme van completándose
            for future in as_completed(future_to_foto):
                foto = future_to_foto[future]
                try:
                    caras_foto = future.result()
                    caras_individuales.extend(caras_foto)
                    print(
                        f"Completado procesamiento de {foto['nombre']}: {len(caras_foto)} caras")
                except Exception as e:
                    print(f"Error procesando {foto['nombre']}: {e}")

        # Log de rendimiento
        end_time = time.time()
        processing_time = end_time - start_time
        print(
            f"RESULTADO FINAL: {len(caras_individuales)} caras procesadas en {processing_time:.2f} segundos")
        log_user_action(user['id'], 'FACIAL_RECOGNITION_COMPLETED',
                        f'Processed {len(fotos_a_procesar)} photos, {len(caras_individuales)} faces in {processing_time:.2f}s')

        return render_template('etiquetar_caras_individuales.html',
                               caras=caras_individuales,
                               user=user)

    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message='Error procesando reconocimiento facial'), 500

def mostrar_resumen_fotos_procesadas(fotos_procesadas, user, conn):
    """Mostrar resumen de fotos que ya tienen personas identificadas"""
    try:
        import json
        cursor = conn.cursor()

        resumen_fotos = []

        for foto in fotos_procesadas:
            # Parsear personas_ids
            try:
                personas_ids = json.loads(
                    foto['personas_ids']) if foto['personas_ids'] else []
            except:
                personas_ids = []

            # Obtener nombres de las personas
            personas_nombres = []
            if personas_ids:
                placeholders = ','.join(['%s' for _ in personas_ids])
                cursor.execute(f'''
                    SELECT id, nombre FROM personas 
                    WHERE id IN ({placeholders})
                ''', personas_ids)
                personas = cursor.fetchall()

                personas_nombres = [p[1] for p in personas]

            resumen_fotos.append({
                'foto_id': foto['id'],
                'foto_nombre': foto['nombre'],
                'foto_url': foto['nombre_archivo'],
                'personas_count': len(personas_nombres),
                'personas_nombres': personas_nombres
            })

        return render_template('resumen_fotos_procesadas.html',
                               fotos=resumen_fotos,
                               user=user)

    except Exception as e:
        print(f"Error mostrando resumen: {e}")
        return render_template('error.html', message='Error mostrando resumen de fotos'), 500

@app.route('/api/debug-info')
def api_debug_info():
    """Endpoint para debugging de información"""
    try:
        # Obtener foto ID 31
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, nombre, nombre_archivo FROM photos WHERE id = 31')
        foto = cursor.fetchone()

        if not foto:
            return {"error": "Foto no encontrada"}, 404

        # Información básica
        info = {
            "foto_id": foto[0],
            "foto_nombre": foto[1],
            "foto_url": foto[2],
            "face_api_key": os.getenv('FACEPP_API_KEY')[:10] + "..." if os.getenv('FACEPP_API_KEY') else "No encontrada",
            "cloudinary_configured": bool(os.getenv('CLOUDINARY_CLOUD_NAME'))
        }

        return info

    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/api/test-one-face')
def api_test_one_face():
    """Procesar solo UNA cara para debugging"""
    try:
        # Obtener foto ID 31
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, nombre, nombre_archivo FROM photos WHERE id = 31')
        foto = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE id = 1')
        user_row = cursor.fetchone()

        if not foto or not user_row:
            return {"error": "Foto o usuario no encontrado"}, 404

        # Convertir usuario a dict
        user_columns = [desc[0] for desc in cursor.description]
        user = dict(zip(user_columns, user_row))

        # Descargar imagen
        img_response = requests.get(foto[2])
        if img_response.status_code != 200:
            return {"error": "Error descargando imagen"}, 400

        # Face++
        api_key = os.getenv('FACEPP_API_KEY')
        api_secret = os.getenv('FACEPP_API_SECRET')

        from io import BytesIO
        files = {'image_file': BytesIO(img_response.content)}
        params = {
            'api_key': api_key,
            'api_secret': api_secret,
            'return_attributes': 'age,gender'
        }

        response = requests.post('https://api-us.faceplusplus.com/facepp/v3/detect',
                                 files=files, data=params, timeout=30)
        face_result = response.json()

        if 'faces' not in face_result or len(face_result['faces']) == 0:
            return {"error": "No se detectaron caras"}, 400

        # Procesar SOLO la primera cara
        cara = face_result['faces'][0]
        face_rectangle = cara['face_rectangle']

        print(f"Procesando cara con rectángulo: {face_rectangle}")

        # PIL processing
        from PIL import Image
        import uuid

        image = Image.open(BytesIO(img_response.content))
        print(f"Imagen PIL: {image.width}x{image.height}")

        # Recortar
        left = face_rectangle['left']
        top = face_rectangle['top']
        width = face_rectangle['width']
        height = face_rectangle['height']

        padding = int(min(width, height) * 0.1)
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(image.width, left + width + (padding * 2))
        bottom = min(image.height, top + height + (padding * 2))

        print(
            f"Coordenadas de recorte: ({left}, {top}) -> ({right}, {bottom})")

        face_crop = image.crop((left, top, right, bottom))
        face_crop = face_crop.resize((200, 200), Image.Resampling.LANCZOS)

        print(f"Recorte creado: {face_crop.width}x{face_crop.height}")

        # Buffer
        buffer = BytesIO()
        face_crop.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)

        print(f"Buffer creado: {len(buffer.getvalue())} bytes")

        # Cloudinary
        temp_filename = f"temp_face_{uuid.uuid4().hex[:8]}.jpg"
        print(f"Subiendo a Cloudinary: {temp_filename}")

        upload_result = cloudinary.uploader.upload(
            buffer,
            folder="temp_faces",
            public_id=temp_filename,
            resource_type="image",
            format="jpg"
        )

        print(f"Resultado Cloudinary: {upload_result}")

        if not upload_result.get('secure_url'):
            return {"error": "Error subiendo a Cloudinary"}, 500

        # Crear array con una sola cara
        caras_individuales = [{
            'foto_id': foto[0],
            'foto_nombre': foto[1],
            'cara_index': 0,
            'face_token': cara['face_token'],
            'recorte_url': upload_result['secure_url'],
            'recorte_public_id': upload_result['public_id'],
            'cara_id': f"{foto[0]}_0"
        }]

        print(f"Array de caras creado: {len(caras_individuales)} elementos")
        print(f"Primera cara URL: {caras_individuales[0]['recorte_url']}")

        # Renderizar template
        return render_template('etiquetar_caras_individuales.html',
                               caras=caras_individuales,
                               user=user)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route('/api/test-face-json')
def api_test_face_json():
    """Endpoint que devuelve JSON para debugging"""
    try:
        # Obtener foto ID 31
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, nombre, nombre_archivo FROM photos WHERE id = 31')
        foto = cursor.fetchone()

        if not foto:
            return {"error": "Foto no encontrada"}, 404

        result = {
            "foto_id": foto[0],
            "foto_nombre": foto[1],
            "foto_url": foto[2],
            "paso": "inicio"
        }

        # Descargar imagen
        img_response = requests.get(foto[2])
        if img_response.status_code != 200:
            result["error"] = f"Error descargando imagen: {img_response.status_code}"
            return result, 400

        result["imagen_descargada"] = f"{len(img_response.content)} bytes"
        result["paso"] = "imagen_descargada"

        # Probar Face++
        api_key = os.getenv('FACEPP_API_KEY')
        api_secret = os.getenv('FACEPP_API_SECRET')

        from io import BytesIO
        files = {'image_file': BytesIO(img_response.content)}
        params = {
            'api_key': api_key,
            'api_secret': api_secret,
            'return_attributes': 'age,gender'
        }

        response = requests.post('https://api-us.faceplusplus.com/facepp/v3/detect',
                                 files=files, data=params, timeout=30)
        face_result = response.json()

        result["face_api_status"] = response.status_code
        result["face_api_response"] = face_result
        result["paso"] = "face_api_completado"

        if 'faces' in face_result:
            result["caras_detectadas"] = len(face_result['faces'])
        else:
            result["caras_detectadas"] = 0

        return result

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }, 500

@app.route('/api/test-face-simple')
def api_test_face_simple():
    """Endpoint simple para probar Face++ con método de archivo"""
    try:
        # Obtener foto ID 31
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, nombre, nombre_archivo FROM photos WHERE id = 31')
        foto = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE id = 1')
        user_row = cursor.fetchone()

        if not foto or not user_row:
            return {"error": "Foto o usuario no encontrado"}, 404

        # Convertir usuario a dict
        user_columns = [desc[0] for desc in cursor.description]
        user = dict(zip(user_columns, user_row))

        print(f"Procesando foto: {foto[1]}")
        print(f"URL: {foto[2]}")

        # Usar el método de tu ejemplo: descargar imagen y enviar archivo
        api_key = os.getenv('FACEPP_API_KEY')
        api_secret = os.getenv('FACEPP_API_SECRET')

        # Descargar imagen
        img_response = requests.get(foto[2])
        if img_response.status_code != 200:
            return {"error": "No se pudo descargar la imagen"}, 400

        print(f"Imagen descargada: {len(img_response.content)} bytes")

        # Enviar archivo a Face++ (método de tu ejemplo)
        from io import BytesIO
        files = {'image_file': BytesIO(img_response.content)}
        params = {
            'api_key': api_key,
            'api_secret': api_secret,
            'return_attributes': 'age,gender'
        }

        print("Enviando archivo a Face++...")
        response = requests.post('https://api-us.faceplusplus.com/facepp/v3/detect',
                                 files=files, data=params, timeout=30)
        result = response.json()

        print(f"Respuesta Face++: {result}")

        if 'faces' not in result or len(result['faces']) == 0:
            return render_template('etiquetar_caras_individuales.html', caras=[], user=user)

        faces = result['faces']
        print(f"Detectadas {len(faces)} caras")

        caras_individuales = []

        # Procesar cada cara
        for idx, cara in enumerate(faces):
            try:
                from PIL import Image
                import uuid

                face_rectangle = cara['face_rectangle']

                # Abrir imagen con PIL
                image = Image.open(BytesIO(img_response.content))

                # Recortar cara
                left = face_rectangle['left']
                top = face_rectangle['top']
                width = face_rectangle['width']
                height = face_rectangle['height']

                padding = int(min(width, height) * 0.1)
                left = max(0, left - padding)
                top = max(0, top - padding)
                right = min(image.width, left + width + (padding * 2))
                bottom = min(image.height, top + height + (padding * 2))

                face_crop = image.crop((left, top, right, bottom))
                face_crop = face_crop.resize(
                    (200, 200), Image.Resampling.LANCZOS)

                # Convertir a buffer
                buffer = BytesIO()
                face_crop.save(buffer, format='JPEG', quality=90)
                buffer.seek(0)

                # Subir a Cloudinary
                temp_filename = f"temp_face_{uuid.uuid4().hex[:8]}.jpg"
                upload_result = cloudinary.uploader.upload(
                    buffer,
                    folder="temp_faces",
                    public_id=temp_filename,
                    resource_type="image",
                    format="jpg"
                )

                if upload_result.get('secure_url'):
                    caras_individuales.append({
                        'foto_id': foto[0],
                        'foto_nombre': foto[1],
                        'cara_index': idx,
                        'face_token': cara['face_token'],
                        'recorte_url': upload_result['secure_url'],
                        'recorte_public_id': upload_result['public_id'],
                        'cara_id': f"{foto[0]}_{idx}"
                    })
                    print(
                        f"Cara {idx + 1} procesada: {upload_result['secure_url']}")

            except Exception as e:
                print(f"Error procesando cara {idx + 1}: {e}")

        print(f"RESULTADO: {len(caras_individuales)} caras procesadas")

        return render_template('etiquetar_caras_individuales.html',
                               caras=caras_individuales,
                               user=user)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route('/api/test-gestionar-personas')
def api_test_gestionar_personas():
    """Probar gestión de personas sin autenticación"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = 1')
        user_row = cursor.fetchone()

        # Convertir usuario a dict
        user_columns = [desc[0] for desc in cursor.description]
        user = dict(zip(user_columns, user_row))

        # Obtener todas las personas
        cursor.execute('''
            SELECT id, nombre, imagen, created_at 
            FROM personas 
            ORDER BY nombre
        ''')
        personas = cursor.fetchall()

        # Convertir a lista de diccionarios
        personas_list = []
        columns = [desc[0] for desc in cursor.description]
        for persona in personas:
            persona_dict = dict(zip(columns, persona))
            personas_list.append({
                'id': persona_dict['id'],
                'nombre': persona_dict['nombre'],
                'imagen': persona_dict['imagen'],
                'created_at': persona_dict['created_at']
            })

        return render_template('gestionar_personas.html', personas=personas_list, user=user)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route('/api/test-foto-procesada')
def api_test_foto_procesada():
    """Probar foto ya procesada sin autenticación"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = 1')
        user_row = cursor.fetchone()

        # Convertir usuario a dict
        user_columns = [desc[0] for desc in cursor.description]
        user = dict(zip(user_columns, user_row))

        # Obtener foto ID 1 que ya tiene personas
        cursor.execute(
            'SELECT id, nombre, nombre_archivo, personas_ids FROM photos WHERE id = 1')
        foto = cursor.fetchone()

        if not foto:
            return {"error": "Foto no encontrada"}, 404

        # Convertir foto a dict
        foto_columns = [desc[0] for desc in cursor.description]
        foto_dict = dict(zip(foto_columns, foto))

        print(f"Foto ID 1 - personas_ids: {foto_dict['personas_ids']}")

        # Verificar si tiene personas
        if foto_dict['personas_ids'] and foto_dict['personas_ids'].strip() and foto_dict['personas_ids'] != 'null':
            print("Foto ya procesada, mostrando resumen")
            return mostrar_resumen_fotos_procesadas([foto_dict], user, conn)
        else:
            print("Foto sin procesar")
            return {"message": "Foto sin procesar"}

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route('/api/test-procesar-reconocimiento-facial')
def api_test_procesar_reconocimiento_facial():
    """API de prueba para procesar reconocimiento facial SIN autenticación"""
    try:
        # Obtener usuario ID 1 para pruebas
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = 1')
        user_row = cursor.fetchone()

        if not user_row:
            return render_template('error.html', message='Usuario no encontrado'), 404

        # Convertir usuario a dict
        user_columns = [desc[0] for desc in cursor.description]
        user = dict(zip(user_columns, user_row))

        # Obtener IDs de fotos específicas desde la query string
        ids_param = request.args.get('ids', '')
        print(f"📋 IDs recibidos en parámetro: '{ids_param}'")

        foto_ids = ids_param.split(',')
        foto_ids = [id.strip() for id in foto_ids if id.strip().isdigit()]

        print(f"📋 IDs procesados: {foto_ids}")

        if not foto_ids:
            print("❌ No hay IDs válidos para procesar")
            return render_template('etiquetar_caras_individuales.html', caras=[], user=user)

        # Obtener la foto específica
        placeholders = ','.join(['%s' for _ in foto_ids])
        cursor.execute(f'''
            SELECT id, nombre, nombre_archivo, mes, año, created_at
            FROM photos 
            WHERE id IN ({placeholders}) AND user_id = %s
            ORDER BY created_at DESC
        ''', foto_ids + [user['id']])
        fotos_recientes = cursor.fetchall()

        print(f"📸 Fotos encontradas: {len(fotos_recientes)}")

        caras_individuales = []

        # Procesar cada foto usando el código que sabemos que funciona
        columns = [desc[0] for desc in cursor.description]
        for foto in fotos_recientes:
            foto_dict = dict(zip(columns, foto))
            print(f"🔍 Procesando foto: {foto_dict['nombre']}")
            print(f"🔗 URL: {foto_dict['nombre_archivo']}")

            # Usar la misma lógica que en debug_processing.py
            api_key = os.getenv('FACEPP_API_KEY')
            api_secret = os.getenv('FACEPP_API_SECRET')

            if not api_key or not api_secret:
                print("❌ Face++ credentials not found")
                continue

            # Detectar caras
            detect_url = "https://api-us.faceplusplus.com/facepp/v3/detect"
            data = {
                'api_key': api_key,
                'api_secret': api_secret,
                'image_url': foto_dict['nombre_archivo'],
                'return_attributes': 'age,gender'
            }

            try:
                print(f"📡 Enviando request a Face++...")
                response = requests.post(detect_url, data=data, timeout=30)
                result = response.json()

                print(f"📥 Respuesta Face++: {result}")

                if 'faces' in result and len(result['faces']) > 0:
                    faces = result['faces']
                    print(f"✅ Detectadas {len(faces)} caras")

                    # Procesar cada cara
                    for idx, cara in enumerate(faces):
                        print(f"✂️ Procesando cara {idx + 1}")

                        face_rectangle = cara['face_rectangle']
                        face_token = cara['face_token']

                        # Crear recorte usando PIL
                        from PIL import Image
                        from io import BytesIO

                        img_response = requests.get(foto_dict['nombre_archivo'])
                        if img_response.status_code == 200:
                            image = Image.open(BytesIO(img_response.content))

                            # Recortar cara
                            left = face_rectangle['left']
                            top = face_rectangle['top']
                            width = face_rectangle['width']
                            height = face_rectangle['height']

                            padding = int(min(width, height) * 0.1)
                            left = max(0, left - padding)
                            top = max(0, top - padding)
                            right = min(image.width, left +
                                        width + (padding * 2))
                            bottom = min(image.height, top +
                                         height + (padding * 2))

                            face_crop = image.crop((left, top, right, bottom))
                            face_crop = face_crop.resize(
                                (200, 200), Image.Resampling.LANCZOS)

                            # Convertir a buffer
                            buffer = BytesIO()
                            face_crop.save(buffer, format='JPEG', quality=90)
                            buffer.seek(0)

                            # Subir a Cloudinary
                            import uuid
                            temp_filename = f"temp_face_{uuid.uuid4().hex[:8]}.jpg"

                            upload_result = cloudinary.uploader.upload(
                                buffer,
                                folder="temp_faces",
                                public_id=temp_filename,
                                resource_type="image",
                                format="jpg"
                            )

                            if upload_result.get('secure_url'):
                                caras_individuales.append({
                                    'foto_id': foto_dict['id'],
                                    'foto_nombre': foto_dict['nombre'],
                                    'cara_index': idx,
                                    'face_token': face_token,
                                    'recorte_url': upload_result['secure_url'],
                                    'recorte_public_id': upload_result['public_id'],
                                    'cara_id': f"{foto_dict['id']}_{idx}"
                                })
                                print(
                                    f"✅ Cara {idx + 1} procesada: {upload_result['secure_url']}")
                            else:
                                print(f"❌ Error subiendo cara {idx + 1}")
                        else:
                            print(
                                f"❌ Error descargando imagen para cara {idx + 1}")
                else:
                    print(f"ℹ️ No se detectaron caras en {foto_dict['nombre']}")

            except Exception as e:
                print(f"❌ Error procesando {foto_dict['nombre']}: {e}")

        print(f"🎯 RESUMEN FINAL:")
        print(f"   - Fotos procesadas: {len(fotos_recientes)}")
        print(f"   - Caras individuales generadas: {len(caras_individuales)}")

        return render_template('etiquetar_caras_individuales.html',
                               caras=caras_individuales,
                               user=user)

    except Exception as e:
        print(f"❌ Error en endpoint de prueba: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', message='Error procesando reconocimiento facial'), 500

@app.route('/api/guardar-etiquetas-personas', methods=['POST'])
@require_auth
def api_guardar_etiquetas_personas():
    """API para guardar etiquetas de personas en fotos"""
    try:
        user = get_current_user()
        data = request.get_json()
        etiquetas = data.get('etiquetas', [])

        print(f"🚀 INICIO - Guardar etiquetas personas")
        print(f"👤 Usuario: {user['name']} (ID: {user['id']})")
        print(f"📝 Datos recibidos: {data}")
        print(f"🏷️ Etiquetas a procesar: {len(etiquetas)}")

        if not etiquetas:
            print("⚠️ No hay etiquetas para guardar")
            return jsonify({'success': True, 'message': 'No hay etiquetas para guardar'})

        conn = get_db()
        cursor = conn.cursor()
        personas_creadas = 0
        fotos_actualizadas = 0

        for etiqueta in etiquetas:
            foto_id = etiqueta['foto_id']
            personas_nombres = etiqueta['personas']
            personas_ids = []

            # Obtener datos de la foto para crear recortes
            cursor.execute(
                'SELECT nombre_archivo FROM photos WHERE id = %s AND user_id = %s',
                (foto_id, user['id'])
            )
            foto_data = cursor.fetchone()

            if not foto_data:
                continue

            # Detectar caras de nuevo para obtener coordenadas de recorte
            print(
                f"🔍 Detectando caras para recortes en foto {foto_id}: {foto_data[0]}")
            caras_detectadas = detect_faces_facepp(foto_data[0])
            print(
                f"📊 Caras detectadas para recortes: {len(caras_detectadas) if caras_detectadas else 0}")

            # Para cada persona mencionada en la foto
            for idx, nombre in enumerate(personas_nombres):
                nombre = nombre.strip()
                if not nombre:
                    continue

                print(f"👤 Procesando persona: '{nombre}' (índice {idx})")

                # Verificar si la persona ya existe
                cursor.execute(
                    'SELECT id, imagen FROM personas WHERE nombre = %s', (
                        nombre,)
                )
                persona_existente = cursor.fetchone()

                if persona_existente:
                    print(
                        f"✅ Persona existente encontrada: ID={persona_existente[0]}, imagen={persona_existente[1] or 'SIN IMAGEN'}")
                    personas_ids.append(persona_existente[0])

                    # Si la persona existe pero no tiene imagen, agregar recorte
                    if not persona_existente[1] and idx < len(caras_detectadas):
                        print(
                            f"🖼️ Creando recorte para persona existente: {nombre} (índice {idx})")
                        face_token = caras_detectadas[idx]['face_token']
                        print(f"🔑 Face token: {face_token}")

                        face_crop = get_face_crop_from_facepp(
                            foto_data[0], face_token)

                        if face_crop:
                            print(
                                f"✂️ Recorte obtenido de Face++, subiendo a Cloudinary...")
                            upload_result = upload_face_crop_to_cloudinary(
                                face_crop, nombre)
                            if upload_result['success']:
                                # Actualizar persona con imagen de recorte
                                cursor.execute('''
                                    UPDATE personas 
                                    SET imagen = %s, updated_at = %s
                                    WHERE id = %s
                                ''', (upload_result['url'], datetime.now(), persona_existente[0]))
                                print(
                                    f"✅ Recorte guardado para persona existente: {nombre} -> {upload_result['url']}")
                            else:
                                print(
                                    f"❌ Error subiendo recorte para {nombre}: {upload_result.get('error', 'Unknown error')}")
                        else:
                            print(
                                f"❌ No se pudo obtener recorte de Face++ para {nombre}")
                    else:
                        if persona_existente[1]:
                            print(
                                f"ℹ️ Persona {nombre} ya tiene imagen: {persona_existente[1]}")
                        else:
                            print(
                                f"⚠️ No hay cara detectada para índice {idx} (total: {len(caras_detectadas)})")
                else:
                    # Crear nueva persona con recorte de cara
                    imagen_url = None

                    # Si hay cara detectada para esta persona, crear recorte
                    if idx < len(caras_detectadas):
                        face_token = caras_detectadas[idx]['face_token']
                        print(
                            f"🖼️ Creando recorte para nueva persona: {nombre} con face_token: {face_token}")

                        face_crop = get_face_crop_from_facepp(
                            foto_data[0], face_token)

                        if face_crop:
                            upload_result = upload_face_crop_to_cloudinary(
                                face_crop, nombre)
                            if upload_result['success']:
                                imagen_url = upload_result['url']
                                print(
                                    f"✅ Recorte creado para nueva persona: {nombre} -> {imagen_url}")
                            else:
                                print(
                                    f"❌ Error subiendo recorte para nueva persona {nombre}: {upload_result.get('error', 'Unknown error')}")
                        else:
                            print(
                                f"❌ No se pudo obtener recorte de Face++ para nueva persona {nombre}")

                    # Crear nueva persona con o sin imagen
                    cursor.execute('''
                        INSERT INTO personas (nombre, imagen, created_at, updated_at)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    ''', (nombre, imagen_url, datetime.now(), datetime.now()))

                    new_person_id = cursor.fetchone()[0]
                    personas_ids.append(new_person_id)
                    personas_creadas += 1

            # Actualizar la foto con las personas identificadas
            if personas_ids:
                personas_ids_json = json.dumps(personas_ids)
                cursor.execute('''
                    UPDATE photos 
                    SET personas_ids = %s, updated_at = %s
                    WHERE id = %s AND user_id = %s
                ''', (personas_ids_json, datetime.now(), foto_id, user['id']))
                fotos_actualizadas += 1

        conn.commit()

        log_user_action(user['id'], 'SAVE_PERSON_TAGS',
                        f'Created {personas_creadas} persons, updated {fotos_actualizadas} photos')

        return jsonify({
            'success': True,
            'message': f'Etiquetas guardadas: {personas_creadas} personas nuevas, {fotos_actualizadas} fotos actualizadas',
            'stats': {
                'personas_creadas': personas_creadas,
                'fotos_actualizadas': fotos_actualizadas
            }
        })

    except Exception as e:
        log_error('api_guardar_etiquetas_personas', e,
                  f'User: {user["id"] if user else "Unknown"}')
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@app.route('/api/guardar-identificaciones-caras', methods=['POST'])
@require_auth
def api_guardar_identificaciones_caras():
    """API para guardar identificaciones de caras individuales"""
    user = None
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Usuario no autenticado'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400
            
        identificaciones = data.get('identificaciones', [])

        print(f"🚀 INICIO - Guardar identificaciones de caras")
        print(f"👤 Usuario: {user['name']} (ID: {user['id']})")
        print(f"🏷️ Identificaciones a procesar: {len(identificaciones)}")

        if not identificaciones:
            print("⚠️ No hay identificaciones para guardar")
            return jsonify({'success': True, 'message': 'No hay identificaciones para guardar'})

        conn = get_db()
        cursor = conn.cursor()
        personas_creadas = 0
        fotos_actualizadas = {}  # Dict para evitar duplicados por foto

        for identificacion in identificaciones:
            try:
                nombre = identificacion['nombre'].strip()
                foto_id = identificacion['foto_id']
                recorte_url = identificacion['recorte_url']
                recorte_public_id = identificacion['recorte_public_id']

                if not nombre:
                    continue

                print(
                    f"👤 Procesando identificación: '{nombre}' para foto {foto_id}")

                # Verificar si la persona ya existe
                cursor.execute(
                    'SELECT id, imagen FROM personas WHERE nombre = %s', (nombre,)
                )
                persona_existente = cursor.fetchone()

                if persona_existente:
                    print(
                        f"✅ Persona existente: {nombre} (ID: {persona_existente[0]})")
                    persona_id = persona_existente[0]

                    # Si no tiene imagen, usar el recorte como imagen permanente
                    if not persona_existente[1]:
                        # Mover de temp_faces a personas
                        try:
                            # Copiar imagen a carpeta personas
                            import uuid
                            new_filename = f"person_{nombre.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.jpg"

                            copy_result = cloudinary.uploader.upload(
                                recorte_url,
                                folder="personas",
                                public_id=new_filename,
                                resource_type="image",
                                format="jpg"
                            )

                            if copy_result.get('secure_url'):
                                # Actualizar persona con nueva imagen
                                cursor.execute('''
                                    UPDATE personas 
                                    SET imagen = %s, updated_at = %s
                                    WHERE id = %s
                                ''', (copy_result['secure_url'], datetime.now(), persona_id))
                                print(
                                    f"✅ Imagen actualizada para {nombre}: {copy_result['secure_url']}")

                            # Eliminar imagen temporal
                            cloudinary.uploader.destroy(recorte_public_id)

                        except Exception as e:
                            print(f"⚠️ Error moviendo imagen para {nombre}: {e}")

                else:
                    # Crear nueva persona con el recorte como imagen
                    print(f"🆕 Creando nueva persona: {nombre}")

                    # Mover imagen de temp_faces a personas
                    imagen_url = None
                    try:
                        import uuid
                        new_filename = f"person_{nombre.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.jpg"

                        copy_result = cloudinary.uploader.upload(
                            recorte_url,
                            folder="personas",
                            public_id=new_filename,
                            resource_type="image",
                            format="jpg"
                        )

                        if copy_result.get('secure_url'):
                            imagen_url = copy_result['secure_url']
                            print(
                                f"✅ Imagen copiada para nueva persona {nombre}: {imagen_url}")

                        # Eliminar imagen temporal
                        cloudinary.uploader.destroy(recorte_public_id)

                    except Exception as e:
                        print(
                            f"⚠️ Error copiando imagen para nueva persona {nombre}: {e}")

                    # Crear persona
                    cursor.execute('''
                        INSERT INTO personas (nombre, imagen, created_at, updated_at)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    ''', (nombre, imagen_url, datetime.now(), datetime.now()))

                    persona_id = cursor.fetchone()[0]
                    personas_creadas += 1
                    print(f"✅ Nueva persona creada: {nombre} (ID: {persona_id})")

                # Agregar persona a la foto (evitar duplicados)
                if foto_id not in fotos_actualizadas:
                    fotos_actualizadas[foto_id] = []
                fotos_actualizadas[foto_id].append(persona_id)

            except KeyError as e:
                print(f"⚠️ Error en identificación, falta clave: {e}")
                continue
            except Exception as e:
                print(f"⚠️ Error procesando identificación: {e}")
                continue

        # Actualizar fotos con personas identificadas
        for foto_id, personas_ids in fotos_actualizadas.items():
            try:
                # Obtener personas_ids existentes
                cursor.execute(
                    'SELECT personas_ids FROM photos WHERE id = %s AND user_id = %s',
                    (foto_id, user['id'])
                )
                foto_actual = cursor.fetchone()

                personas_existentes = []
                if foto_actual and foto_actual[0]:
                    try:
                        # En PostgreSQL, los datos JSON se pueden almacenar como texto
                        # pero también se pueden manejar como objetos JSON
                        if isinstance(foto_actual[0], str):
                            personas_existentes = json.loads(foto_actual[0])
                        else:
                            # Si ya es una lista (caso poco probable pero por si acaso)
                            personas_existentes = list(foto_actual[0]) if isinstance(foto_actual[0], (list, tuple)) else []
                    except Exception as e:
                        print(f"⚠️ Error parseando personas_ids: {e}")
                        personas_existentes = []

                # Combinar con nuevas personas (evitar duplicados)
                todas_personas = list(set(personas_existentes + personas_ids))
                personas_ids_json = json.dumps(todas_personas)

                cursor.execute('''
                    UPDATE photos 
                    SET personas_ids = %s, updated_at = %s
                    WHERE id = %s AND user_id = %s
                ''', (personas_ids_json, datetime.now(), foto_id, user['id']))

                print(
                    f"✅ Foto {foto_id} actualizada con personas: {todas_personas}")

            except Exception as e:
                print(f"⚠️ Error actualizando foto {foto_id}: {e}")
                continue

        conn.commit()

        log_user_action(user['id'], 'SAVE_FACE_IDENTIFICATIONS',
                        f'Created {personas_creadas} persons, updated {len(fotos_actualizadas)} photos')

        return jsonify({
            'success': True,
            'message': f'Identificaciones guardadas: {personas_creadas} personas nuevas, {len(fotos_actualizadas)} fotos actualizadas',
            'stats': {
                'personas_creadas': personas_creadas,
                'fotos_actualizadas': len(fotos_actualizadas)
            }
        })

    except Exception as e:
        log_error('api_guardar_identificaciones_caras', e,
                  f'User: {user["id"] if user else "Unknown"}')
        # Devolver un mensaje más específico si es posible
        error_message = 'Error interno del servidor'
        if user is None:
            error_message = 'Error de autenticación'
        return jsonify({'success': False, 'message': error_message}), 500

@app.route('/robots.txt')
def robots_txt():
    """Servir robots.txt para SEO"""
    return app.send_static_file('robots.txt')

@app.route('/init-db')
def init_db_route():
    init_db()
    return "Database initialized"

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app_logger.info("APLICACION INICIADA")
    app.run( host='0.0.0.0', port=8000)
