<?php
// Pantalla Empresa (Suscriptor Plan Pro) — Mokana
// Protegida por sesión PHP desde public/index.php
?>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Panel Empresa: Mokana</title>
  <meta name="description" content="Panel empresarial multitenant de Mokana para monitoreo de alertas de manglares en zonas contratadas y trazabilidad ESG." />
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Geologica:wght,CRSV,SHRP@200..500,0,0..100&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/assets/css/tokens.css" />
  <link rel="stylesheet" href="/assets/css/base.css" />
  <link rel="stylesheet" href="/assets/css/panel.css" />
</head>
<body data-panel="empresa">
  <div class="app-shell">
    <aside id="sidebar" class="sidebar" aria-label="Navegación Empresa" data-open="false">
      <div class="sidebar-brand">
        <a class="brand-lockup" href="#dashboard" aria-label="Mokana Empresa">
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

        <button type="button" class="nav-item" data-view="suscripcion">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <rect x="2" y="5" width="20" height="14" rx="2" /><line x1="2" y1="10" x2="22" y2="10" />
          </svg>
          <span>Mi suscripción</span>
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
          <span class="user-name">Puerto Verde Logística</span>
          <span class="user-role">operaciones@puertoverde.com</span>
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
            <input id="search-global" type="search" class="search-input" placeholder="Buscar alerta en tus zonas" aria-label="Buscar alerta en tus zonas" />
          </div>
        </div>
        <div class="topbar-right">
          <div id="net-status" class="status-chip" role="status" aria-live="polite" data-offline="false">
            <span id="net-label">En línea</span>
          </div>
          <span class="profile-pill">Empresa (Plan Pro)</span>
        </div>
      </header>

      <main id="main-content" class="content" data-fullbleed="false">
        <!-- DASHBOARD OPCIÓN 2 (EMPRESA) -->
        <section id="view-dashboard" class="view-panel" data-active="true" aria-labelledby="dash-heading">
          <div class="hero-band">
            <article class="ticks hero-status-card">
              <div>
                <h1 id="dash-heading" class="page-title">Monitoreo empresarial de manglares</h1>
                <p class="page-subtitle">Alertas verificadas en tiempo real para Ciénaga de Mallorquín y Puerto Velero.</p>
              </div>
              <div class="hero-figures">
                <div class="hero-metric">
                  <span class="metric-label">Alertas en tus zonas</span>
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
                <h2 class="panel-title">Mapa de zonas contratadas</h2>
                <div class="toolbar-row">
                  <button id="zoom-out" type="button" class="btn-line btn-icon" aria-label="Alejar">-</button>
                  <button id="zoom-reset" type="button" class="btn-line">100%</button>
                  <button id="zoom-in" type="button" class="btn-line btn-icon" aria-label="Acercar">+</button>
                  <button id="btn-maximize-map" type="button" class="btn-line">Maximizar</button>
                </div>
              </div>
              <div id="dash-map-viewport" class="map-viewport" role="region" aria-label="Mapa de zonas contratadas">
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
              <h2 class="panel-title">Zonas contratadas</h2>
              <hr class="band-divider" />
              <div class="metric-value num">2<span class="u">sectores</span></div>
              <span class="ruled-desc">Ciénaga de Mallorquín y Puerto Velero / Balboa</span>
            </article>

            <article class="ticks band-card">
              <h2 class="panel-title">Bonos de carbono ESG</h2>
              <hr class="band-divider" />
              <div class="metric-value num">1,280<span class="u">tCO₂</span></div>
              <span class="ruled-desc">Cobertura Plan Pro verificada</span>
            </article>

            <article class="ticks band-card">
              <h2 class="panel-title">Última alerta IA</h2>
              <hr class="band-divider" />
              <div id="dash-last-ai" class="metric-value num">En espera</div>
              <span id="dash-last-ai-sub" class="ruled-desc">Solo alertas Alta y Crítica de tus zonas</span>
            </article>
          </div>
        </section>

        <!-- MAPA EN VIVO 100% PURO -->
        <section id="view-mapa" class="view-panel view-panel--map-only" data-active="false" aria-label="Mapa en vivo">
          <div id="pure-map-viewport" class="map-viewport map-viewport--pure">
            <div id="pure-map-stage" class="map-stage" data-dragging="false">
              <img class="map-base" src="/assets/img/map/relieve.jpg" alt="Mapa completo del Atlántico" width="691" height="641" draggable="false" />
              <img class="map-overlay" src="/assets/img/map/plan.png" alt="" width="691" height="641" draggable="false" />
              <div id="pure-map-pins" class="map-pins"></div>
            </div>
          </div>
        </section>

        <!-- GESTIÓN DE ALERTAS OPCIÓN 3 (EMPRESA) -->
        <section id="view-alertas" class="view-panel" data-active="false" aria-labelledby="alertas-heading">
          <div class="page-head">
            <div>
              <h1 id="alertas-heading" class="page-title">Gestión de Alertas</h1>
              <p class="page-subtitle">Alertas Alta y Crítica verificadas por IA en tus sectores contratados.</p>
            </div>
            <button id="btn-refresh-api" type="button" class="btn-line">Actualizar desde API</button>
          </div>

          <div class="escalation-grid" role="group" aria-label="Criterio de escalamiento">
            <button type="button" class="esc-card esc-card--critical" data-sev="CRÍTICA" aria-pressed="false">
              <span class="esc-title">Crítica</span>
              <span id="esc-cnt-critica" class="esc-count">0</span>
              <span class="esc-rule">Incluida en Plan Pro</span>
            </button>
            <button type="button" class="esc-card esc-card--high" data-sev="ALTA" aria-pressed="false">
              <span class="esc-title">Alta</span>
              <span id="esc-cnt-alta" class="esc-count">0</span>
              <span class="esc-rule">Incluida en Plan Pro</span>
            </button>
            <button type="button" class="esc-card esc-card--moderate" data-sev="MEDIA" aria-pressed="false">
              <span class="esc-title">Media</span>
              <span id="esc-cnt-media" class="esc-count">0</span>
              <span class="esc-rule">Disponible en Enterprise</span>
            </button>
            <button type="button" class="esc-card esc-card--low" data-sev="BAJA" aria-pressed="false">
              <span class="esc-title">Baja</span>
              <span id="esc-cnt-baja" class="esc-count">0</span>
              <span class="esc-rule">Disponible en Enterprise</span>
            </button>
          </div>

          <article class="ticks">
            <div class="panel-head">
              <h2 class="panel-title">Registro de alertas activas (Plan Pro)</h2>
              <span id="alerts-count-label" class="ruled-desc num">0 registros</span>
            </div>

            <div id="alerts-empty" class="empty-box">
              <strong>Sin alertas activas en tus zonas contratadas.</strong>
              <span class="ruled-desc">Las alertas Alta y Crítica de Ciénaga de Mallorquín y Puerto Velero aparecerán aquí en vivo al ser verificadas por el Bot Agente IA.</span>
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

        <!-- MI SUSCRIPCIÓN -->
        <section id="view-suscripcion" class="view-panel" data-active="false" aria-labelledby="sub-heading">
          <div class="page-head">
            <div>
              <h1 id="sub-heading" class="page-title">Mi suscripción</h1>
              <p class="page-subtitle">Alcance activo para Puerto Verde Logística.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="ruled-list">
              <div class="ruled-row">
                <span class="ruled-copy"><span class="ruled-title">Plan contratado</span><span class="ruled-desc">Monitoreo en vivo de alertas Alta y Crítica</span></span>
                <span class="badge badge--BAJA">Plan Pro activo</span>
              </div>
              <div class="ruled-row">
                <span class="ruled-copy"><span class="ruled-title">Zonas asignadas</span><span class="ruled-desc">Aislamiento multitenant por contrato</span></span>
                <span class="num">Ciénaga de Mallorquín, Puerto Velero</span>
              </div>
            </div>
          </article>
        </section>

        <!-- BONOS DE CARBONO -->
        <section id="view-bonos" class="view-panel" data-active="false" aria-labelledby="bonos-heading">
          <div class="page-head">
            <div>
              <h1 id="bonos-heading" class="page-title">Bonos de carbono ESG</h1>
              <p class="page-subtitle">Trazabilidad de biomasa y carbono azul en tus sectores.</p>
            </div>
          </div>
          <article class="ticks band-card">
            <h2 class="panel-title">Stock monitoreado</h2>
            <hr class="band-divider" />
            <div class="metric-value num">1,280<span class="u">tCO₂</span></div>
            <span class="ruled-desc">Respaldo técnico conectado a los informes de la API Mokaná</span>
          </article>
        </section>

        <!-- EXPORTAR INFORMES -->
        <section id="view-exportar" class="view-panel" data-active="false" aria-labelledby="export-heading">
          <div class="page-head">
            <div>
              <h1 id="export-heading" class="page-title">Exportar informes</h1>
              <p class="page-subtitle">Descarga datos filtrados exclusivamente a tus zonas contratadas.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="export-grid">
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Tabla analítica CSV</strong>
                  <span class="ruled-desc">Alertas Alta y Crítica de tus sectores.</span>
                </div>
                <button id="exp-csv" type="button" class="btn-pill">Descargar CSV</button>
              </div>
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Capa geográfica GeoJSON</strong>
                  <span class="ruled-desc">Coordenadas georreferenciadas para reportes ESG.</span>
                </div>
                <button id="exp-geojson" type="button" class="btn-line">Descargar GeoJSON</button>
              </div>
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Informe ejecutivo PDF</strong>
                  <span class="ruled-desc">Imprime o guarda tu reporte corporativo en PDF.</span>
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
      <h2 id="dialog-map-title" class="panel-title">Mapa de zonas contratadas</h2>
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

  <!-- Diálogo Informe Técnico IA (Solo lectura) -->
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
