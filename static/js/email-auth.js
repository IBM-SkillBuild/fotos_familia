/**
 * Autenticación por Email
 */

// Variables globales para el proceso de autenticación
let currentAction = null; // 'login' o 'register'
let currentUserData = {};

/**
 * Procesar registro de usuario con backend
 */
async function processRegister(name, email) {
    try {
        console.log('🔄 Enviando registro al backend:', { name, email });
        
        // Validar datos antes de enviar
        if (!name || !email) {
            throw new Error('Nombre o email no proporcionados');
        }

        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, email })
        });
        
        // Verificar si la respuesta es exitosa
        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Error ${response.status}: ${response.statusText}`);
            console.error('Respuesta del servidor:', errorData);
            
            // Manejar error específico de email duplicado
            if (response.status === 409 && errorData.code === 'EMAIL_ALREADY_EXISTS') {
                return {
                    success: false,
                    error: 'EMAIL_EXISTS',
                    message: errorData.message,
                    suggestion: errorData.suggestion
                };
            }
            
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('📥 Respuesta del backend:', data);
        
        if (data.success) {
            currentAction = 'register';
            currentUserData = { name, email };
            return {
                success: true,
                message: data.message,
                email: email,
                name: name
            };
        } else {
            return {
                success: false,
                message: data.message,
                suggestion: data.suggestion
            };
        }
    } catch (error) {
        console.error('❌ Error en processRegister:', error);
        return {
            success: false,
            message: `Error de conexión: ${error.message}`
        };
    }
}

/**
 * Procesar login de usuario con backend
 */
async function processLogin(email) {
    try {
        console.log('🔄 Enviando login al backend:', { email });
        
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        console.log('📥 Respuesta del backend:', data);
        
        if (data.success) {
            // Proceder con verificación de email
            currentAction = 'login';
            currentUserData = { email, name: data.user_name };
            return {
                success: true,
                message: data.message,
                email: email,
                name: data.user_name
            };
        } else {
            return {
                success: false,
                message: data.message,
                suggestion: data.suggestion
            };
        }
    } catch (error) {
        console.error('❌ Error en processLogin:', error);
        return {
            success: false,
            message: 'Error de conexión. Inténtalo de nuevo.'
        };
    }
}

/**
 * Verificar código de email con backend
 */
async function processEmailVerification(code) {
    try {
        console.log('🔄 Verificando código:', { code, action: currentAction, userData: currentUserData });
        
        const response = await fetch('/api/auth/verify-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: currentUserData.email,
                code: code,
                action: currentAction
            })
        });
        
        const data = await response.json();
        console.log('📥 Respuesta verificación:', data);
        
        if (data.success) {
            // Autenticación exitosa
            return {
                success: true,
                message: data.message,
                user: data.user
            };
        } else {
            return {
                success: false,
                message: data.message
            };
        }
        
    } catch (error) {
        console.error('❌ Error en processEmailVerification:', error);
        return {
            success: false,
            message: 'Error procesando verificación'
        };
    }
}

/**
 * Reenviar código de email
 */
async function resendEmailCode() {
    if (!currentUserData.email) {
        return {
            success: false,
            message: 'No hay email para reenviar'
        };
    }
    
    // Reenviar usando el mismo proceso según la acción
    if (currentAction === 'register') {
        return await processRegister(currentUserData.name, currentUserData.email);
    } else {
        return await processLogin(currentUserData.email);
    }
}

console.log('✅ Email Auth cargado correctamente');