(() => {
  "use strict";

  document.documentElement.classList.add("js-ready");

  const tenantSwitch = document.getElementById("tenant-switch");
  const tenantButtons = document.querySelectorAll(".tenant-btn");
  const tenantInput = document.getElementById("tenant-type");
  const emailLabel = document.getElementById("email-label");
  const emailInput = document.getElementById("email");
  const emailMessage = document.getElementById("email-message");
  const passwordInput = document.getElementById("password");
  const passwordMessage = document.getElementById("password-message");
  const togglePasswordBtn = document.getElementById("toggle-password");
  const eyeOpenIcon = document.getElementById("icon-eye-open");
  const eyeClosedIcon = document.getElementById("icon-eye-closed");
  const loginForm = document.getElementById("login-form");
  const submitBtn = document.getElementById("submit-btn");
  const submitLabel = document.getElementById("submit-label");
  const formNotice = document.getElementById("form-notice");

  const TENANT_COPY = {
    cra: {
      label: "Correo institucional",
      placeholder: "nombre@cra.gov.co",
    },
    subscriber: {
      label: "Correo corporativo",
      placeholder: "equipo@empresa.com",
    },
  };

  const touched = {
    email: false,
    password: false,
  };

  function setTenant(mode) {
    const config = TENANT_COPY[mode] || TENANT_COPY.cra;
    tenantSwitch.dataset.active = mode;
    tenantInput.value = mode;

    tenantButtons.forEach((btn) => {
      const isActive = btn.dataset.tenant === mode;
      btn.setAttribute("aria-pressed", String(isActive));
    });

    emailLabel.textContent = config.label;
    emailInput.placeholder = config.placeholder;
  }

  tenantButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setTenant(btn.dataset.tenant);
    });
  });

  togglePasswordBtn.addEventListener("click", () => {
    const showing = passwordInput.type === "text";
    passwordInput.type = showing ? "password" : "text";
    togglePasswordBtn.setAttribute("aria-pressed", String(!showing));
    togglePasswordBtn.setAttribute(
      "aria-label",
      showing ? "Mostrar contraseña" : "Ocultar contraseña"
    );
    eyeOpenIcon.style.display = showing ? "block" : "none";
    eyeClosedIcon.style.display = showing ? "none" : "block";
  });

  function validateEmail() {
    const val = emailInput.value.trim();
    const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
    if (!val) {
      emailInput.setAttribute("aria-invalid", "true");
      emailMessage.textContent = "Ingresa tu correo.";
      emailMessage.classList.add("field-message--error");
      return false;
    }
    if (!isValid) {
      emailInput.setAttribute("aria-invalid", "true");
      emailMessage.textContent = "Formato de correo inválido.";
      emailMessage.classList.add("field-message--error");
      return false;
    }
    emailInput.removeAttribute("aria-invalid");
    emailMessage.textContent = "";
    emailMessage.classList.remove("field-message--error");
    return true;
  }

  function validatePassword() {
    const val = passwordInput.value;
    if (!val) {
      passwordInput.setAttribute("aria-invalid", "true");
      passwordMessage.textContent = "Ingresa tu contraseña.";
      passwordMessage.classList.add("field-message--error");
      return false;
    }
    if (val.length < 8) {
      passwordInput.setAttribute("aria-invalid", "true");
      passwordMessage.textContent = "Mínimo 8 caracteres.";
      passwordMessage.classList.add("field-message--error");
      return false;
    }
    passwordInput.removeAttribute("aria-invalid");
    passwordMessage.textContent = "";
    passwordMessage.classList.remove("field-message--error");
    return true;
  }

  emailInput.addEventListener("blur", () => {
    touched.email = true;
    validateEmail();
  });

  emailInput.addEventListener("input", () => {
    if (touched.email) validateEmail();
  });

  passwordInput.addEventListener("blur", () => {
    touched.password = true;
    validatePassword();
  });

  passwordInput.addEventListener("input", () => {
    if (touched.password) validatePassword();
  });

  loginForm.addEventListener("submit", (event) => {
    const endpoint = loginForm.dataset.endpoint || "";
    const emailOk = validateEmail();
    const passOk = validatePassword();
    touched.email = true;
    touched.password = true;

    if (!emailOk || !passOk) {
      event.preventDefault();
      if (!emailOk) {
        emailInput.focus();
      } else {
        passwordInput.focus();
      }
      return;
    }

    if (!endpoint) {
      event.preventDefault();
      submitBtn.disabled = true;
      submitBtn.dataset.loading = "true";
      submitLabel.textContent = "Verificando…";

      window.setTimeout(() => {
        submitBtn.disabled = false;
        submitBtn.dataset.loading = "false";
        submitLabel.textContent = "Ingresar";
        formNotice.dataset.tone = "info";
        formNotice.dataset.visible = "true";
        formNotice.textContent = "Preview lista para conectar a /auth/login.php.";
      }, 450);
    }
  });
})();
