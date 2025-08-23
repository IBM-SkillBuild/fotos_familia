/**
 * Lógica del Modal de Autenticación
 */

// Estado del modal
let authModalState = {
    currentStep: 'selection',
    isLoading: false,
    currentEmail: '',
    currentName: ''
};

/**
 * Mostrar el modal de autenticación
 */
function showAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.style.display = 'block';
        showAuthSelection();
    }
}

/**
 * Ocultar el modal de autenticación
 */
function hideAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.style.display = 'none';
        resetAuthModal();
    }
}

/**
 * Resetear el modal a su estado inicial
 */
function resetAuthModal() {
    authModalState = {
        currentStep: 'selection',
        isLoading: false,
        currentEmail: '',
        currentName: ''
    };
    
    // Limpiar formularios
    document.querySelectorAll('#authModal form').forEach(form => form.reset());
    
    // Limpiar alertas
    clearAuthAlerts();
    
    // Mostrar paso inicial
    showAuthSelection();
}

/**
 * Mostrar paso de selección
 */
function showAuthSelection() {
    hideAllAuthSteps();
    document.getElementById('auth-selection').classList.add('active');
    document.getElementById('authModalTitle').textContent = 'Bienvenido';
    authModalState.currentStep = 'selection';
}

/**
 * Mostrar formulario de login
 */
function showLoginForm() {
    hideAllAuthSteps();
    document.getElementById('login-form').classList.add('active');
    document.getElementById('authModalTitle').textContent = 'Iniciar Sesión';
    document.getElementById('loginEmail').focus();
    authModalState.currentStep = 'login';
}

/**
 * Mostrar formulario de registro
 */
function showRegisterForm() {
    hideAllAuthSteps();
    document.getElementById('register-form').classList.add('active');
    document.getElementById('authModalTitle').textContent = 'Crear Cuenta';
    document.getElementById('registerName').focus();
    authModalState.currentStep = 'register';
}

/**
 * Mostrar paso de verificación Email
 */
function showEmailVerification(email) {
    hideAllAuthSteps();
    document.getElementById('email-verification').classList.add('active');
    document.getElementById('authModalTitle').textContent = 'Verificación Email';
    document.getElementById('verificationEmail').textContent = email;
    document.getElementById('emailCode').focus();
    authModalState.currentStep = 'verification';
    authModalState.currentEmail = email;
}

/**
 * Ocultar todos los pasos del modal
 */
function hideAllAuthSteps() {
    document.querySelectorAll('.auth-step').forEach(step => {
        step.classList.remove('active');
    });
}

/**
 * Mostrar alerta en el modal
 */
function showAuthAlert(message, type = 'danger', suggestion = null) {
    const alertContainer = document.getElementById('authAlerts');
    
    let suggestionHtml = '';
    if (suggestion === 'login') {
        suggestionHtml = '<br><button class="btn btn-link btn-sm p-0 mt-1" onclick="showLoginForm()">¿Quieres iniciar sesión?</button>';
    } else if (suggestion === 'register') {
        suggestionHtml = '<br><button class="btn btn-link btn-sm p-0 mt-1" onclick="showRegisterForm()">¿Quieres crear una cuenta?</button>';
    }
    
    alertContainer.innerHTML = `
        <div class="alert alert-${type} alert-auth alert-dismissible fade show" role="alert">
            ${message}${suggestionHtml}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
}

/**
 * Mostrar alerta específica para email existente
 */
function showEmailExistsAlert(email) {
    const alertContainer = document.getElementById('authAlerts');
    
    alertContainer.innerHTML = `
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <div class="d-flex align-items-center mb-2">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Este email ya está registrado</strong>
            </div>
            <p class="mb-2">El email <strong>${email}</strong> ya tiene una cuenta.</p>
            <div class="d-grid gap-2">
                <button type="button" class="btn btn-primary btn-sm" onclick="switchToLoginWithEmail('${email}')">
                    <i class="fas fa-sign-in-alt me-1"></i>
                    Iniciar sesión con este email
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="clearRegisterForm()">
                    <i class="fas fa-edit me-1"></i>
                    Usar otro email
                </button>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
}

/**
 * Cambiar a login con email pre-rellenado
 */
function switchToLoginWithEmail(email) {
    showLoginForm();
    document.getElementById('loginEmail').value = email;
    clearAuthAlerts();
}

/**
 * Limpiar formulario de registro
 */
function clearRegisterForm() {
    document.getElementById('registerName').value = '';
    document.getElementById('registerEmail').value = '';
    clearAuthAlerts();
}

/**
 * Limpiar alertas del modal
 */
function clearAuthAlerts() {
    document.getElementById('authAlerts').innerHTML = '';
}

/**
 * Establecer estado de carga en un botón
 */
function setButtonLoading(buttonId, loading) {
    const button = document.getElementById(buttonId);
    if (button) {
        button.disabled = loading;
        const spinner = button.querySelector('.spinner-border');
        const text = button.querySelector('.btn-text');
        
        if (loading) {
            spinner.classList.remove('d-none');
            text.style.display = 'none';
        } else {
            spinner.classList.add('d-none');
            text.style.display = 'inline';
        }
    }
    authModalState.isLoading = loading;
}

/**
 * Manejar envío del formulario de login
 */
async function handleLoginSubmit(event) {
    event.preventDefault();
    
    if (authModalState.isLoading) return;
    
    const email = document.getElementById('loginEmail').value.trim();
    
    if (!email) {
        showAuthAlert('Por favor ingresa tu email');
        return;
    }
    
    setButtonLoading('loginSubmitBtn', true);
    clearAuthAlerts();
    
    try {
        const result = await processLogin(email);
        
        if (result.success) {
            showAuthAlert('Código enviado a tu email', 'success');
            setTimeout(() => {
                showEmailVerification(email);
            }, 1500);
        } else {
            showAuthAlert(result.message, 'danger', result.suggestion);
        }
    } catch (error) {
        showAuthAlert('Error de conexión. Inténtalo de nuevo.');
    } finally {
        setButtonLoading('loginSubmitBtn', false);
    }
}

/**
 * Manejar envío del formulario de registro
 */
async function handleRegisterSubmit(event) {
    event.preventDefault();
    
    if (authModalState.isLoading) return;
    
    const name = document.getElementById('registerName').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    
    if (!name || !email) {
        showAuthAlert('Por favor completa todos los campos');
        return;
    }
    
    setButtonLoading('registerSubmitBtn', true);
    clearAuthAlerts();
    
    try {
        const result = await processRegister(name, email);
        
        if (result.success) {
            showAuthAlert('Código enviado a tu email', 'success');
            authModalState.currentName = name;
            setTimeout(() => {
                showEmailVerification(email);
            }, 1500);
        } else if (result.error === 'EMAIL_EXISTS') {
            // Mostrar mensaje específico para email duplicado
            showEmailExistsAlert(email);
        } else {
            showAuthAlert(result.message, 'danger', result.suggestion);
        }
    } catch (error) {
        showAuthAlert('Error de conexión. Inténtalo de nuevo.');
    } finally {
        setButtonLoading('registerSubmitBtn', false);
    }
}

/**
 * Manejar verificación Email
 */
async function handleEmailVerification(event) {
    event.preventDefault();
    
    if (authModalState.isLoading) return;
    
    const code = document.getElementById('emailCode').value.trim();
    
    if (!code || code.length !== 6) {
        showAuthAlert('Por favor ingresa un código de 6 dígitos');
        return;
    }
    
    setButtonLoading('emailVerifyBtn', true);
    clearAuthAlerts();
    
    try {
        const result = await processEmailVerification(code);
        
        if (result.success) {
            showAuthAlert(`¡Bienvenido, ${result.user.name}!`, 'success');
            setTimeout(() => {
                hideAuthModal();
                // Recargar página para mostrar dashboard
                window.location.reload();
            }, 2000);
        } else {
            showAuthAlert(result.message);
        }
    } catch (error) {
        showAuthAlert('Error verificando código. Inténtalo de nuevo.');
    } finally {
        setButtonLoading('emailVerifyBtn', false);
    }
}

/**
 * Reenviar código Email (wrapper para UI)
 */
async function handleResendEmailCode() {
    if (authModalState.isLoading) return;
    
    clearAuthAlerts();
    showAuthAlert('Reenviando código...', 'info');
    
    try {
        const result = await resendEmailCode();
        
        if (result.success) {
            showAuthAlert('Código reenviado correctamente', 'success');
        } else {
            showAuthAlert(result.message);
        }
    } catch (error) {
        showAuthAlert('Error reenviando código');
    }
}

/**
 * Inicializar eventos del modal cuando se carga la página
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 Inicializando auth-modal.js');
    
    // Event listeners para formularios
    const loginForm = document.getElementById('loginFormElement');
    const registerForm = document.getElementById('registerFormElement');
    const emailForm = document.getElementById('emailVerificationForm');
    
    console.log('📋 Formularios encontrados:', {
        loginForm: !!loginForm,
        registerForm: !!registerForm,
        emailForm: !!emailForm
    });
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLoginSubmit);
        console.log('✅ Event listener agregado a loginForm');
    }
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegisterSubmit);
        console.log('✅ Event listener agregado a registerForm');
    }
    
    if (emailForm) {
        emailForm.addEventListener('submit', handleEmailVerification);
        console.log('✅ Event listener agregado a emailForm');
    }
    
    // Auto-focus en código Email cuando se muestra
    const emailCodeInput = document.getElementById('emailCode');
    if (emailCodeInput) {
        emailCodeInput.addEventListener('input', function(e) {
            // Solo permitir números
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
        });
    }
});