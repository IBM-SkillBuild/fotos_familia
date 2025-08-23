"""
Servicio de Email para autenticación
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from logger_config import (
    log_email_attempt, log_email_success, log_email_error, 
    log_smtp_config, email_logger
)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_email = os.getenv('SMTP_EMAIL')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_name = os.getenv('SMTP_FROM_NAME', 'Auth App')
        
    def is_configured(self):
        """Verificar si SMTP está configurado"""
        return bool(self.smtp_email and self.smtp_password)
    
    def send_verification_code(self, to_email, name, code):
        """Enviar código de verificación por email"""
        try:
            # Log del intento
            log_email_attempt(to_email, name, code)
            log_smtp_config(self.smtp_server, self.smtp_port, self.smtp_email, bool(self.smtp_password))
            
            if not self.is_configured():
                error_msg = "SMTP no configurado - faltan credenciales"
                log_email_error(to_email, error_msg)
                return False
                
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Código de verificación: {code}'
            msg['From'] = f'{self.from_name} <{self.smtp_email}>'
            msg['To'] = to_email
            
            # Plantilla HTML
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                    .content {{ padding: 30px; }}
                    .code-box {{ background: #f8f9fa; border: 2px dashed #007bff; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
                    .code {{ font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 5px; }}
                    .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 Código de Verificación</h1>
                        <p>Hola {name}, aquí tienes tu código</p>
                    </div>
                    <div class="content">
                        <p>Has solicitado acceso a tu cuenta. Usa el siguiente código para completar la verificación:</p>
                        
                        <div class="code-box">
                            <div class="code">{code}</div>
                            <p style="margin: 10px 0 0 0; color: #666;">Código de 6 dígitos</p>
                        </div>
                        
                        <p><strong>⏰ Este código expira en 10 minutos</strong></p>
                        <p>Si no solicitaste este código, puedes ignorar este email.</p>
                    </div>
                    <div class="footer">
                        <p>📧 Email enviado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</p>
                        <p>🔒 Este es un email automático, no respondas a este mensaje</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Versión texto plano
            text_body = f"""
            Código de Verificación
            
            Hola {name},
            
            Tu código de verificación es: {code}
            
            Este código expira en 10 minutos.
            
            Si no solicitaste este código, ignora este email.
            
            ---
            Email enviado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}
            """
            
            # Adjuntar ambas versiones
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # Enviar email
            email_logger.info(f"Conectando a {self.smtp_server}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()  # Identificarse primero
                server.starttls()  # Iniciar TLS
                server.ehlo()  # Identificarse de nuevo después de TLS
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(msg)
            
            log_email_success(to_email)
            return True
            
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            log_email_error(to_email, f"{type(e).__name__}: {str(e)}")
            email_logger.error(f"Traceback completo:\n{traceback_str}")
            return False

# Instancia global
email_service = EmailService()