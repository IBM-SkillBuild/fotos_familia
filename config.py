"""
Configuración para la aplicación Flask SMS Auth
"""
import os
from datetime import timedelta

class Config:
    # Clave secreta para sesiones
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-2024')
    
    # Configuración de base de datos
    DATABASE = 'users.db'
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = False  # True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_NAME = 'sms_auth_session'
    
    # Configuración de desarrollo
    DEBUG = True
    PORT = 5001
    HOST = '0.0.0.0'

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Debe estar definida en producción