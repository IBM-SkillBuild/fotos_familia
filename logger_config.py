"""
Configuración de logging para la aplicación
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger():
    """Configurar sistema de logging"""
    
    # Crear directorio de logs si no existe
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configurar formato de logs (sin emojis para compatibilidad)
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Logger principal de la aplicación
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.DEBUG)
    
    # Logger para emails
    email_logger = logging.getLogger('email')
    email_logger.setLevel(logging.DEBUG)
    
    # Handler para archivo general (rotativo)
    app_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setFormatter(log_format)
    app_handler.setLevel(logging.INFO)
    
    # Handler para emails específicamente
    email_handler = RotatingFileHandler(
        'logs/email.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    email_handler.setFormatter(log_format)
    email_handler.setLevel(logging.DEBUG)
    
    # Handler para errores críticos
    error_handler = RotatingFileHandler(
        'logs/errors.log',
        maxBytes=5*1024*1024,   # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setFormatter(log_format)
    error_handler.setLevel(logging.ERROR)
    
    # Handler para consola (desarrollo) - solo texto simple
    console_handler = logging.StreamHandler()
    console_format = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    console_handler.setLevel(logging.INFO)
    
    # Agregar handlers
    app_logger.addHandler(app_handler)
    app_logger.addHandler(error_handler)
    app_logger.addHandler(console_handler)
    
    email_logger.addHandler(email_handler)
    email_logger.addHandler(error_handler)
    email_logger.addHandler(console_handler)
    
    # Evitar duplicación de logs
    app_logger.propagate = False
    email_logger.propagate = False
    
    return app_logger, email_logger

# Configurar loggers globales
app_logger, email_logger = setup_logger()

def log_request(endpoint, method, data=None):
    """Log de requests HTTP"""
    app_logger.info(f"REQUEST {method} {endpoint} - Data: {data}")

def log_response(endpoint, status_code, message=None):
    """Log de responses HTTP"""
    app_logger.info(f"RESPONSE {endpoint} - Status: {status_code} - Message: {message}")

def log_error(context, error, traceback_str=None):
    """Log de errores"""
    app_logger.error(f"ERROR in {context}: {str(error)}")
    if traceback_str:
        app_logger.error(f"TRACEBACK: {traceback_str}")

def log_email_attempt(to_email, name, code):
    """Log de intento de envío de email"""
    email_logger.info(f"EMAIL ATTEMPT - To: {to_email}, Name: {name}, Code: {code}")

def log_email_success(to_email):
    """Log de email enviado exitosamente"""
    email_logger.info(f"EMAIL SUCCESS - Sent to: {to_email}")

def log_email_error(to_email, error):
    """Log de error en envío de email"""
    email_logger.error(f"EMAIL ERROR - To: {to_email}, Error: {str(error)}")

def log_smtp_config(server, port, email, has_password):
    """Log de configuración SMTP"""
    email_logger.info(f"SMTP CONFIG - Server: {server}:{port}, Email: {email}, Password: {'Yes' if has_password else 'No'}")

def log_user_action(user_id, action, details=None):
    """Log de acciones de usuario"""
    app_logger.info(f"USER ACTION - ID: {user_id}, Action: {action}, Details: {details}")

def log_session_event(user_id, event, token_preview=None):
    """Log de eventos de sesión"""
    app_logger.info(f"SESSION {event} - User: {user_id}, Token: {token_preview}")

def log_database_operation(operation, table, details=None):
    """Log de operaciones de base de datos"""
    app_logger.debug(f"DB {operation} - Table: {table}, Details: {details}")