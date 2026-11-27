<?php
declare(strict_types=1);
// Vista validada: Pantalla 1 — Login Multitenant (Mokana)
// Variables esperadas desde el controlador PHP:
//   $csrfToken  (string) Token CSRF de sesión
//   $flashError (string|null) Mensaje de error de autenticación
//   $oldEmail   (string) Último correo ingresado
//   $oldTenant  (string) 'cra' | 'subscriber'
$csrfToken  = $csrfToken  ?? '';
$flashError = $flashError ?? null;
$oldEmail   = $oldEmail   ?? '';
$oldTenant  = ($oldTenant ?? 'cra') === 'subscriber' ? 'subscriber' : 'cra';
$emailLabel = $oldTenant === 'subscriber' ? 'Correo corporativo' : 'Correo institucional';
$emailPh    = $oldTenant === 'subscriber' ? 'equipo@empresa.com' : 'nombre@cra.gov.co';
?>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Iniciar sesión: Mokana</title>
  <meta
    name="description"
    content="Acceso al panel administrativo multitenant de Mokana."
  />
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=Plus+Jakarta+Sans:wght@600;700&display=swap"
    rel="stylesheet"
  />
  <link rel="stylesheet" href="/assets/css/tokens.css" />
  <link rel="stylesheet" href="/assets/css/base.css" />
  <link rel="stylesheet" href="/assets/css/login.css" />
</head>
<body>
  <main class="auth-shell">
    <section class="auth-card" aria-labelledby="login-heading">
      <header class="auth-brand reveal-item" style="--i: 0">
        <svg
          class="auth-topo"
          viewBox="0 0 460 130"
          fill="none"
          aria-hidden="true"
          preserveAspectRatio="xMidYMid slice"
        >
          <path
            d="M-20 28 C 40 12, 72 64, 132 42 C 192 20, 218 -10, 278 16"
            stroke="currentColor"
            stroke-width="1.2"
          />
          <path
            d="M-20 56 C 54 34, 88 92, 152 66 C 216 40, 240 10, 312 34"
            stroke="currentColor"
            stroke-width="1.1"
          />
          <path
            d="M-20 88 C 68 62, 108 118, 178 90 C 248 62, 272 34, 344 58"
            stroke="currentColor"
            stroke-width="1"
          />
          <path
            d="M270 124 C 322 92, 356 108, 412 72 C 442 52, 462 42, 480 46"
            stroke="currentColor"
            stroke-width="1.2"
          />
          <path
            d="M310 132 C 358 106, 392 118, 444 86 C 462 74, 474 68, 485 70"
            stroke="currentColor"
            stroke-width="1"
          />
        </svg>

        <a class="auth-logo-link" href="#login-heading" aria-label="Mokana">
          <img
            class="auth-isotipo"
            src="/assets/img/mokana-isotipo-verde.svg"
            alt=""
            width="64"
            height="64"
          />
          <span class="auth-wordmark">Mokana</span>
        </a>
      </header>

      <div class="auth-body">
        <h1 id="login-heading" class="auth-title reveal-item" style="--i: 1">
          Iniciar sesión
        </h1>

        <div
          id="tenant-switch"
          class="tenant-switch reveal-item"
          style="--i: 2"
          data-active="<?= htmlspecialchars($oldTenant, ENT_QUOTES, 'UTF-8') ?>"
          role="group"
          aria-label="Tipo de acceso"
        >
          <span class="tenant-indicator" aria-hidden="true"></span>
          <button
            type="button"
            class="tenant-btn"
            data-tenant="cra"
            aria-pressed="<?= $oldTenant === 'cra' ? 'true' : 'false' ?>"
          >
            C.R.A
          </button>
          <button
            type="button"
            class="tenant-btn"
            data-tenant="subscriber"
            aria-pressed="<?= $oldTenant === 'subscriber' ? 'true' : 'false' ?>"
          >
            Empresa
          </button>
        </div>

        <form
          id="login-form"
          class="auth-form reveal-item"
          style="--i: 3"
          method="post"
          action="/auth/login.php"
          data-endpoint="/auth/login.php"
          novalidate
        >
          <input
            type="hidden"
            id="tenant-type"
            name="tenant_type"
            value="<?= htmlspecialchars($oldTenant, ENT_QUOTES, 'UTF-8') ?>"
          />
          <input
            type="hidden"
            name="csrf_token"
            value="<?= htmlspecialchars($csrfToken, ENT_QUOTES, 'UTF-8') ?>"
          />

          <div
            id="form-notice"
            class="form-notice"
            role="status"
            aria-live="polite"
            data-visible="<?= $flashError ? 'true' : 'false' ?>"
            data-tone="<?= $flashError ? 'error' : 'info' ?>"
          ><?= $flashError ? htmlspecialchars($flashError, ENT_QUOTES, 'UTF-8') : '' ?></div>

          <div class="field-group">
            <label id="email-label" class="field-label" for="email">
              <?= htmlspecialchars($emailLabel, ENT_QUOTES, 'UTF-8') ?>
            </label>
            <div class="field-control">
              <input
                id="email"
                name="email"
                type="email"
                class="field-input"
                autocomplete="email"
                inputmode="email"
                value="<?= htmlspecialchars($oldEmail, ENT_QUOTES, 'UTF-8') ?>"
                placeholder="<?= htmlspecialchars($emailPh, ENT_QUOTES, 'UTF-8') ?>"
                aria-required="true"
                aria-describedby="email-message"
                required
              />
            </div>
            <p id="email-message" class="field-message"></p>
          </div>

          <div class="field-group">
            <label class="field-label" for="password">Contraseña</label>
            <div class="field-control">
              <input
                id="password"
                name="password"
                type="password"
                class="field-input field-input--with-action"
                autocomplete="current-password"
                placeholder="••••••••"
                aria-required="true"
                aria-describedby="password-message"
                required
              />
              <button
                id="toggle-password"
                type="button"
                class="field-action"
                aria-label="Mostrar contraseña"
                aria-pressed="false"
              >
                <svg
                  id="icon-eye-open"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <svg
                  id="icon-eye-closed"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                  style="display: none"
                >
                  <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                  <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.5 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                  <path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                  <line x1="2" y1="2" x2="22" y2="22" />
                </svg>
              </button>
            </div>
            <p id="password-message" class="field-message"></p>
          </div>

          <button
            id="submit-btn"
            type="submit"
            class="btn-primary"
            data-loading="false"
          >
            <span class="btn-spinner keep-motion" aria-hidden="true"></span>
            <span id="submit-label">Ingresar</span>
          </button>

          <div class="auth-meta-row">
            <a class="auth-link" href="/auth/recuperar.php">¿Olvidaste tu contraseña?</a>
          </div>
        </form>
      </div>
    </section>
  </main>

  <script src="/assets/js/login.js" defer></script>
</body>
</html>
