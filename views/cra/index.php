<?php
// Pantalla C.R.A (Sin cobro · Acceso Total) — Mokana
// Protegida por sesión PHP desde public/index.php
?>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Panel C.R.A: Mokana</title>
  <meta name="description" content="Panel administrativo C.R.A de Mokana para monitoreo en vivo de alertas de manglares validadas por Agente IA." />
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Geologica:wght,CRSV,SHRP@200..500,0,0..100&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/assets/css/tokens.css" />
  <link rel="stylesheet" href="/assets/css/base.css" />
  <link rel="stylesheet" href="/assets/css/panel.css" />
</head>
<body data-panel="cra">
  <div class="app-shell">
    <aside id="sidebar" class="sidebar" aria-label="Navegación C.R.A" data-open="false">
      <div class="sidebar-brand">
        <a class="brand-lockup" href="#dashboard" aria-label="Mokana C.R.A">
          <img class="brand-isotipo" src="/assets/img/mokana-isotipo-verde.svg" alt="" width="34" height="34" />
          <span class="brand-wordmark">Mokana</span>
        </a>
      </div>

      <nav class="sidebar-nav">
        <button type="button" class="nav-item" data-view="dashboard" aria-current="page">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" />
          </svg>
          <span>Dashboard</span>
        </button>

        <button type="button" class="nav-item" data-view="mapa">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
            <line x1="9" y1="3" x2="9" y2="18" /><line x1="15" y1="6" x2="15" y2="21" />
          </svg>
          <span>Mapa en vivo</span>
        </button>

        <button type="button" class="nav-item" data-view="alertas">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>Gestión de Alertas</span>
          <span id="nav-alert-count" class="nav-count">0</span>
        </button>

        <button type="button" class="nav-item" data-view="tenants">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span>Tenants y planes</span>
        </button>

        <button type="button" class="nav-item" data-view="bonos">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
          </svg>
          <span>Bonos de carbono</span>
        </button>

        <button type="button" class="nav-item" data-view="exportar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>Exportar informes</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="user-meta">
          <span class="user-name">Coordinación C.R.A</span>
          <span class="user-role">admin@cra.gov.co</span>
        </div>
        <a class="btn-line btn-icon" href="/auth/logout.php" aria-label="Cerrar sesión" title="Cerrar sesión">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </a>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <button id="menu-toggle" type="button" class="menu-btn" aria-label="Abrir menú" aria-expanded="false">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div class="search-wrap">
            <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input id="search-global" type="search" class="search-input" placeholder="Buscar sector o alerta" aria-label="Buscar sector o alerta" />
          </div>
        </div>
        <div class="topbar-right">
          <div id="net-status" class="status-chip" role="status" aria-live="polite" data-offline="false">
            <span id="net-label">En línea</span>
          </div>
          <span class="profile-pill">C.R.A (Acceso total)</span>
        </div>
      </header>

      <main id="main-content" class="content" data-fullbleed="false">
        <!-- VISTA 1: DASHBOARD OPCIÓN 2 (TABLERO EJECUTIVO EN BANDAS) -->
        <section id="view-dashboard" class="view-panel" data-active="true" aria-labelledby="dash-heading">
          <div class="hero-band">
            <article class="ticks hero-status-card">
              <div>
                <h1 id="dash-heading" class="page-title">Estado del ecosistema del Atlántico</h1>
                <p class="page-subtitle">Monitoreo C.R.A conectado en vivo a la API del Bot Agente IA.</p>
              </div>
              <div class="hero-figures">
                <div class="hero-metric">
                  <span class="metric-label">Alertas activas</span>
                  <div id="dash-active-count" class="metric-value num">0<span class="u">activas</span></div>
                </div>
                <div class="hero-metric">
                  <span class="metric-label">Índice máximo ambiental</span>
                  <div id="dash-max-risk" class="metric-value metric-value--critical num">0<span class="u">/100</span></div>
                </div>
              </div>
              <p id="bot-api-status" class="ruled-desc">Bot IA: Conectando a mokana.joshual.tech</p>
              <div class="toolbar-row">
                <button type="button" class="btn-pill" data-jump-view="alertas">Ir a Gestión de Alertas</button>
                <button type="button" class="btn-line" data-jump-view="mapa">Abrir Mapa en vivo</button>
              </div>
            </article>

            <article class="ticks">
              <div class="panel-head">
                <h2 class="panel-title">Mapa georreferenciado C.R.A</h2>
                <div class="toolbar-row">
                  <button id="zoom-out" type="button" class="btn-line btn-icon" aria-label="Alejar">-</button>
                  <button id="zoom-reset" type="button" class="btn-line">100%</button>
                  <button id="zoom-in" type="button" class="btn-line btn-icon" aria-label="Acercar">+</button>
                  <button id="btn-maximize-map" type="button" class="btn-line">Maximizar</button>
                </div>
              </div>
              <div id="dash-map-viewport" class="map-viewport" role="region" aria-label="Mapa compacto del Atlántico">
                <div id="dash-map-stage" class="map-stage" data-dragging="false">
                  <img class="map-base" src="/assets/img/map/relieve.jpg" alt="Relieve costero del Atlántico" width="691" height="641" draggable="false" />
                  <img class="map-overlay" src="/assets/img/map/plan.png" alt="" width="691" height="641" draggable="false" />
                  <div id="dash-map-pins" class="map-pins"></div>
                </div>
              </div>
              <div class="map-legend">
                <span class="legend-item"><span class="legend-swatch swatch--preservacion"></span>Preservación</span>
                <span class="legend-item"><span class="legend-swatch swatch--restauracion"></span>Restauración</span>
                <span class="legend-item"><span class="legend-swatch swatch--recuperacion"></span>Recuperación</span>
                <span class="legend-item"><span class="legend-swatch swatch--rehabilitacion"></span>Rehabilitación</span>
                <span class="legend-item"><span class="legend-swatch swatch--manglar"></span>Manglar probable</span>
              </div>
            </article>
          </div>

          <div class="lower-band">
            <article class="ticks band-card">
              <h2 class="panel-title">Sectores monitoreados</h2>
              <hr class="band-divider" />
              <div class="metric-value num">5<span class="u">zonas</span></div>
              <span class="ruled-desc">Mallorquín, Balboa, Tubará, Juan de Acosta y Totumo</span>
            </article>

            <article class="ticks band-card">
              <h2 class="panel-title">Bonos de carbono</h2>
              <hr class="band-divider" />
              <div class="metric-value num">1,280<span class="u">tCO₂</span></div>
              <span class="ruled-desc">Trazabilidad ESG y bonos ciudadanos activos</span>
            </article>

            <article class="ticks band-card">
              <h2 class="panel-title">Última respuesta Agente IA</h2>
              <hr class="band-divider" />
              <div id="dash-last-ai" class="metric-value num">En espera</div>
              <span id="dash-last-ai-sub" class="ruled-desc">Sin alertas precargadas hasta prueba.bat</span>
            </article>
          </div>
        </section>

        <!-- VISTA 2: MAPA EN VIVO (100% PURO, SIN FORMULARIO NI CONTROLES EXTRA) -->
        <section id="view-mapa" class="view-panel view-panel--map-only" data-active="false" aria-label="Mapa en vivo del Atlántico">
          <div id="pure-map-viewport" class="map-viewport map-viewport--pure">
            <div id="pure-map-stage" class="map-stage" data-dragging="false">
              <img class="map-base" src="/assets/img/map/relieve.jpg" alt="Mapa completo del Atlántico" width="691" height="641" draggable="false" />
              <img class="map-overlay" src="/assets/img/map/plan.png" alt="" width="691" height="641" draggable="false" />
              <div id="pure-map-pins" class="map-pins"></div>
            </div>
          </div>
        </section>

        <!-- VISTA 3: GESTIÓN DE ALERTAS OPCIÓN 3 (TARJETAS DE ESCALAMIENTO + MONITOREO IA) -->
        <section id="view-alertas" class="view-panel" data-active="false" aria-labelledby="alertas-heading">
          <div class="page-head">
            <div>
              <h1 id="alertas-heading" class="page-title">Gestión de Alertas</h1>
              <p class="page-subtitle">Monitoreo en vivo de alertas clasificadas y validadas por la API del Bot Agente IA.</p>
            </div>
            <button id="btn-refresh-api" type="button" class="btn-line">Actualizar desde API</button>
          </div>

          <div class="escalation-grid" role="group" aria-label="Criterio de escalamiento">
            <button type="button" class="esc-card esc-card--critical" data-sev="CRÍTICA" aria-pressed="false">
              <span class="esc-title">Crítica</span>
              <span id="esc-cnt-critica" class="esc-count">0</span>
              <span class="esc-rule">Despacho inmediato C.R.A</span>
            </button>
            <button type="button" class="esc-card esc-card--high" data-sev="ALTA" aria-pressed="false">
              <span class="esc-title">Alta</span>
              <span id="esc-cnt-alta" class="esc-count">0</span>
              <span class="esc-rule">Prioridad en tiempo real Pro</span>
            </button>
            <button type="button" class="esc-card esc-card--moderate" data-sev="MEDIA" aria-pressed="false">
              <span class="esc-title">Media</span>
              <span id="esc-cnt-media" class="esc-count">0</span>
              <span class="esc-rule">Seguimiento continuo</span>
            </button>
            <button type="button" class="esc-card esc-card--low" data-sev="BAJA" aria-pressed="false">
              <span class="esc-title">Baja</span>
              <span id="esc-cnt-baja" class="esc-count">0</span>
              <span class="esc-rule">Preventivo y trazabilidad ESG</span>
            </button>
          </div>

          <article class="ticks">
            <div class="panel-head">
              <h2 class="panel-title">Registro de alertas activas (Agente IA)</h2>
              <span id="alerts-count-label" class="ruled-desc num">0 registros</span>
            </div>

            <div id="alerts-empty" class="empty-box">
              <strong>Sin alertas activas en este momento.</strong>
              <span class="ruled-desc">Este panel recibe en tiempo real las alertas verificadas por la API del Bot Agente IA. Ejecuta prueba.bat para enviar una alerta de prueba.</span>
            </div>

            <div id="alerts-table-wrap" class="table-scroll" style="display: none">
              <table class="data-table">
                <thead>
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">Sector</th>
                    <th scope="col">Hallazgo</th>
                    <th scope="col">Severidad</th>
                    <th scope="col">Riesgo</th>
                    <th scope="col">Evaluación Bot IA</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Detalle</th>
                  </tr>
                </thead>
                <tbody id="alerts-tbody"></tbody>
              </table>
            </div>
          </article>
        </section>

        <!-- VISTA 4: TENANTS Y PLANES -->
        <section id="view-tenants" class="view-panel" data-active="false" aria-labelledby="tenants-heading">
          <div class="page-head">
            <div>
              <h1 id="tenants-heading" class="page-title">Tenants y planes</h1>
              <p class="page-subtitle">Suscriptores conectados al motor de alertas C.R.A, Empresas B2B y Academia.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th scope="col">Organización</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Plan</th>
                    <th scope="col">Zonas</th>
                    <th scope="col">Estado</th>
                  </tr>
                </thead>
                <tbody id="tenants-tbody"></tbody>
              </table>
            </div>
          </article>
        </section>

        <!-- VISTA 5: BONOS DE CARBONO -->
        <section id="view-bonos" class="view-panel" data-active="false" aria-labelledby="bonos-heading">
          <div class="page-head">
            <div>
              <h1 id="bonos-heading" class="page-title">Bonos de carbono e incentivos</h1>
              <p class="page-subtitle">Trazabilidad de carbono azul empresarial e incentivos ciudadanos.</p>
            </div>
          </div>
          <div class="hero-band">
            <article class="ticks band-card">
              <h2 class="panel-title">Bonos de carbono empresariales</h2>
              <hr class="band-divider" />
              <div class="metric-value num">1,280<span class="u">tCO₂</span></div>
              <span class="ruled-desc">Stock monitoreado con respaldo técnico de alertas C.R.A</span>
            </article>
            <article class="ticks band-card">
              <h2 class="panel-title">Reportes verificados por IA</h2>
              <hr class="band-divider" />
              <div id="bonds-validated-count" class="metric-value num">0<span class="u">reportes</span></div>
              <span class="ruled-desc">Contabilizados para bonos a personas naturales</span>
            </article>
          </div>
        </section>

        <!-- VISTA 6: EXPORTAR INFORMES -->
        <section id="view-exportar" class="view-panel" data-active="false" aria-labelledby="export-heading">
          <div class="page-head">
            <div>
              <h1 id="export-heading" class="page-title">Exportar informes</h1>
              <p class="page-subtitle">Descarga datos técnicos C.R.A de todas las alertas recibidas.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="export-grid">
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Tabla analítica CSV</strong>
                  <span class="ruled-desc">Exporta alertas, severidad, índice de riesgo y confianza IA.</span>
                </div>
                <button id="exp-csv" type="button" class="btn-pill">Descargar CSV</button>
              </div>
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Capa geográfica GeoJSON</strong>
                  <span class="ruled-desc">Coordenadas listas para QGIS o plataforma C.R.A.</span>
                </div>
                <button id="exp-geojson" type="button" class="btn-line">Descargar GeoJSON</button>
              </div>
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Informe ejecutivo PDF</strong>
                  <span class="ruled-desc">Imprime o guarda el resumen oficial en PDF.</span>
                </div>
                <button id="exp-pdf" type="button" class="btn-line">Imprimir PDF</button>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>
  </div>

  <!-- Diálogo Maximizar Mapa -->
  <dialog id="map-dialog" class="native-dialog" aria-labelledby="dialog-map-title">
    <header class="dialog-header">
      <h2 id="dialog-map-title" class="panel-title">Mapa georreferenciado C.R.A</h2>
      <div class="toolbar-row">
        <button id="dialog-zoom-out" type="button" class="btn-line btn-icon" aria-label="Alejar">-</button>
        <button id="dialog-zoom-reset" type="button" class="btn-line">100%</button>
        <button id="dialog-zoom-in" type="button" class="btn-line btn-icon" aria-label="Acercar">+</button>
        <button id="btn-minimize-map" type="button" class="btn-pill">Minimizar</button>
      </div>
    </header>
    <div class="dialog-map-body">
      <div id="dialog-map-viewport" class="map-viewport map-viewport--full">
        <div id="dialog-map-stage" class="map-stage" data-dragging="false">
          <img class="map-base" src="/assets/img/map/relieve.jpg" alt="Relieve del Atlántico" width="691" height="641" draggable="false" />
          <img class="map-overlay" src="/assets/img/map/plan.png" alt="" width="691" height="641" draggable="false" />
          <div id="dialog-map-pins" class="map-pins"></div>
        </div>
      </div>
    </div>
    <footer class="dialog-footer">
      <div class="map-legend">
        <span class="legend-item"><span class="legend-swatch swatch--preservacion"></span>Preservación</span>
        <span class="legend-item"><span class="legend-swatch swatch--restauracion"></span>Restauración</span>
        <span class="legend-item"><span class="legend-swatch swatch--recuperacion"></span>Recuperación</span>
        <span class="legend-item"><span class="legend-swatch swatch--rehabilitacion"></span>Rehabilitación</span>
        <span class="legend-item"><span class="legend-swatch swatch--manglar"></span>Manglar probable</span>
      </div>
    </footer>
  </dialog>

  <!-- Diálogo de Informe Técnico IA (Solo lectura, sin validación manual) -->
  <dialog id="detail-dialog" class="native-dialog native-dialog--detail" aria-labelledby="detail-title">
    <header class="dialog-header">
      <h2 id="detail-title" class="panel-title">Informe técnico Agente IA</h2>
      <button id="btn-close-detail" type="button" class="btn-line">Cerrar</button>
    </header>
    <div id="detail-body" class="dialog-body"></div>
    <footer class="dialog-footer">
      <span class="ruled-desc">Evaluación generada automáticamente por la API del Bot Mokaná.</span>
    </footer>
  </dialog>

  <script src="/assets/js/panel.js" defer></script>
</body>
</html>
