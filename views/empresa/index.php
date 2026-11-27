<?php
// Pantalla Empresa (Suscriptor Plan Pro: Ciénaga de Mallorquín y Puerto Colombia · Con Bonos) — Mokana
?>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Panel Empresa: Mokana</title>
  <meta name="description" content="Panel empresarial de Mokana para monitoreo de alertas en Ciénaga de Mallorquín y Puerto Colombia." />
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Geologica:wght,CRSV,SHRP@200..500,0,0..100&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
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

      <main class="content">
        <!-- DASHBOARD EMPRESA (RESTRINGIDO A MALLORQUÍN Y PUERTO COLOMBIA + BONOS) -->
        <section id="view-dashboard" class="view-panel" data-active="true" aria-labelledby="dash-heading">
          <div class="dash-top-grid">
            <div class="dash-left-stack">
              <article class="ticks ticks--compact eco-compact">
                <div class="panel-head" style="margin-bottom: 0">
                  <h1 id="dash-heading" class="panel-title">Estado del ecosistema contratado</h1>
                  <span id="dash-eco-badge" class="badge badge--BAJA">Estable</span>
                </div>

                <div class="hero-figures">
                  <div class="hero-metric">
                    <span class="metric-label">Alertas activas</span>
                    <div id="dash-active-count" class="metric-value metric-value--sm num">0<span class="u">activas</span></div>
                  </div>
                  <div class="hero-metric">
                    <span class="metric-label">Riesgo general promediado</span>
                    <div id="dash-avg-risk" class="metric-value metric-value--sm metric-value--critical num">0<span class="u">/100</span></div>
                  </div>
                </div>

                <div>
                  <span class="metric-label">Subecosistemas pagados (2 zonas)</span>
                  <div id="subecosystems-list" class="subeco-list"></div>
                </div>

                <div class="toolbar-row">
                  <button type="button" class="btn-pill" data-jump-view="alertas">Ir a Gestión de Alertas</button>
                </div>
              </article>

              <article class="ticks ticks--compact stack-card">
                <div class="stack-copy">
                  <h2 class="ruled-title">Bonos de carbono</h2>
                  <span class="ruled-desc">Cobertura Plan Pro verificada</span>
                </div>
                <div class="metric-value metric-value--sm num">1,280<span class="u">tCO₂</span></div>
              </article>
            </div>

            <article class="ticks dash-map-card">
              <div class="panel-head">
                <h2 class="panel-title">Mapa de zonas de calor contratadas</h2>
                <button id="btn-open-map-modal" type="button" class="btn-line">Ampliar mapa</button>
              </div>
              <div
                id="dash-map-viewport"
                class="map-viewport map-viewport--clickable"
                role="button"
                tabindex="0"
                aria-label="Abrir modal completo del mapa de zonas contratadas"
              ></div>
              <div class="map-legend">
                <span class="legend-item"><span class="legend-swatch swatch--kmz"></span>Prioridades KMZ</span>
                <span class="legend-item"><span class="legend-swatch swatch--heat-low"></span>Baja densidad</span>
                <span class="legend-item"><span class="legend-swatch swatch--heat-mid"></span>Media densidad</span>
                <span class="legend-item"><span class="legend-swatch swatch--heat-high"></span>Alta densidad</span>
              </div>
            </article>
          </div>

          <!-- Últimas 10 alertas -->
          <article class="ticks">
            <div class="panel-head">
              <h2 class="panel-title">Últimas 10 alertas</h2>
              <button type="button" class="btn-line" data-jump-view="alertas">Ver todas</button>
            </div>

            <div id="dash-alerts-empty" class="empty-box">
              <strong>Sin alertas en tus sectores contratados.</strong>
              <span class="ruled-desc">Las alertas de Ciénaga de Mallorquín y Puerto Colombia aparecerán aquí en vivo.</span>
            </div>

            <div id="dash-alerts-table-wrap" class="table-scroll" style="display: none">
              <table class="data-table">
                <thead>
                  <tr>
                    <th scope="col">Radicado</th>
                    <th scope="col">Zona</th>
                    <th scope="col">Anomalía</th>
                    <th scope="col">Prioridad</th>
                    <th scope="col">Informe</th>
                    <th scope="col">Detalle</th>
                  </tr>
                </thead>
                <tbody id="dash-alerts-tbody"></tbody>
              </table>
            </div>
          </article>
        </section>

        <!-- GESTIÓN DE ALERTAS EMPRESA (FILTROS + PAGINADO EXCLUSIVO) -->
        <section id="view-alertas" class="view-panel" data-active="false" aria-labelledby="alertas-heading">
          <div class="page-head">
            <div>
              <h1 id="alertas-heading" class="page-title">Gestión de Alertas</h1>
              <p class="page-subtitle">Alertas activas en Ciénaga de Mallorquín y Puerto Colombia.</p>
            </div>
            <button id="btn-refresh-api" type="button" class="btn-line">Actualizar</button>
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
              <span class="esc-rule">Seguimiento continuo</span>
            </button>
            <button type="button" class="esc-card esc-card--low" data-sev="BAJA" aria-pressed="false">
              <span class="esc-title">Baja</span>
              <span id="esc-cnt-baja" class="esc-count">0</span>
              <span class="esc-rule">Preventivo ESG</span>
            </button>
          </div>

          <article class="ticks">
            <div class="alerts-filter-bar">
              <div class="toolbar-row" role="group" aria-label="Filtrar alertas por prioridad">
                <button type="button" class="btn-line sev-filter-btn" data-sev-filter="" aria-pressed="true">Todas</button>
                <button type="button" class="btn-line sev-filter-btn" data-sev-filter="CRÍTICA" aria-pressed="false">Críticas</button>
                <button type="button" class="btn-line sev-filter-btn" data-sev-filter="ALTA" aria-pressed="false">Altas</button>
                <button type="button" class="btn-line sev-filter-btn" data-sev-filter="MEDIA" aria-pressed="false">Medias</button>
                <button type="button" class="btn-line sev-filter-btn" data-sev-filter="BAJA" aria-pressed="false">Bajas</button>
              </div>
              <span id="alerts-count-label" class="ruled-desc num">0 registros</span>
            </div>

            <div id="alerts-empty" class="empty-box">
              <strong>Sin alertas para el filtro actual.</strong>
              <span class="ruled-desc">Solo se muestran alertas de Ciénaga de Mallorquín y Puerto Colombia.</span>
            </div>

            <div id="alerts-table-wrap" class="table-scroll" style="display: none">
              <table class="data-table">
                <thead>
                  <tr>
                    <th scope="col">Radicado</th>
                    <th scope="col">Zona</th>
                    <th scope="col">Anomalía</th>
                    <th scope="col">Prioridad</th>
                    <th scope="col">Informe</th>
                    <th scope="col">Detalle</th>
                  </tr>
                </thead>
                <tbody id="alerts-tbody"></tbody>
              </table>
            </div>

            <div id="alerts-pagination" class="pagination-bar" style="display: none">
              <span id="pagination-info" class="ruled-desc num"></span>
              <div id="pagination-controls" class="pagination-controls"></div>
            </div>
          </article>
        </section>

        <!-- MI SUSCRIPCIÓN -->
        <section id="view-suscripcion" class="view-panel" data-active="false" aria-labelledby="sub-heading">
          <div class="page-head">
            <div>
              <h1 id="sub-heading" class="page-title">Mi suscripción</h1>
              <p class="page-subtitle">Cobertura contratada para Puerto Verde Logística.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="ruled-list">
              <div class="ruled-row">
                <span class="ruled-copy"><span class="ruled-title">Plan contratado</span><span class="ruled-desc">Monitoreo en vivo de alertas</span></span>
                <span class="badge badge--BAJA">Plan Pro activo</span>
              </div>
              <div class="ruled-row">
                <span class="ruled-copy"><span class="ruled-title">Sectores pagados</span><span class="ruled-desc">Aislamiento multitenant por contrato</span></span>
                <span class="num">Ciénaga de Mallorquín y Puerto Colombia</span>
              </div>
            </div>
          </article>
        </section>

        <!-- BONOS DE CARBONO -->
        <section id="view-bonos" class="view-panel" data-active="false" aria-labelledby="bonos-heading">
          <div class="page-head">
            <div>
              <h1 id="bonos-heading" class="page-title">Bonos de carbono ESG</h1>
              <p class="page-subtitle">Trazabilidad de biomasa en Ciénaga de Mallorquín y Puerto Colombia.</p>
            </div>
          </div>
          <article class="ticks band-card">
            <h2 class="panel-title">Stock monitoreado</h2>
            <hr class="band-divider" />
            <div class="metric-value num">1,280<span class="u">tCO₂</span></div>
            <span class="ruled-desc">Respaldo técnico para reportes ESG</span>
          </article>
        </section>

        <!-- EXPORTAR INFORMES -->
        <section id="view-exportar" class="view-panel" data-active="false" aria-labelledby="export-heading">
          <div class="page-head">
            <div>
              <h1 id="export-heading" class="page-title">Exportar informes</h1>
              <p class="page-subtitle">Descarga datos filtrados exclusivamente a Ciénaga de Mallorquín y Puerto Colombia.</p>
            </div>
          </div>
          <article class="ticks">
            <div class="export-grid">
              <div class="export-option">
                <div class="ruled-copy">
                  <strong class="ruled-title">Tabla analítica CSV</strong>
                  <span class="ruled-desc">Alertas de tus sectores contratados.</span>
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
                  <strong class="ruled-title">Dataset JSON / PDF</strong>
                  <span class="ruled-desc">Dataset abierto JSON o impresión ejecutiva en PDF.</span>
                </div>
                <div class="toolbar-row">
                  <button id="exp-json" type="button" class="btn-line">JSON</button>
                  <button id="exp-pdf" type="button" class="btn-line">PDF</button>
                </div>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>
  </div>

  <!-- MODAL COMPLETO DEL MAPA EMPRESA -->
  <dialog id="map-dialog" class="native-dialog" aria-labelledby="dialog-map-title">
    <header class="dialog-header">
      <h2 id="dialog-map-title" class="panel-title">Mapa de zonas de calor contratadas</h2>
      <div class="map-filter-bar">
        <select id="map-filter-sev" class="filter-select" aria-label="Filtrar por prioridad">
          <option value="">Todas las prioridades</option>
          <option value="CRÍTICA">Crítica</option>
          <option value="ALTA">Alta</option>
          <option value="MEDIA">Media</option>
          <option value="BAJA">Baja</option>
        </select>
        <select id="map-filter-zone" class="filter-select" aria-label="Filtrar por zona">
          <option value="">Mis zonas pagadas</option>
          <option value="zone_mallorquin">Ciénaga de Mallorquín</option>
          <option value="zone_balboa">Puerto Colombia</option>
        </select>
        <button id="btn-toggle-kmz" type="button" class="btn-line" aria-pressed="true">Capa KMZ</button>
        <button id="btn-minimize-map" type="button" class="btn-pill">Cerrar</button>
      </div>
    </header>
    <div class="map-modal-grid">
      <div class="map-modal-canvas">
        <div id="modal-map-viewport" class="map-viewport map-viewport--modal"></div>
      </div>

      <aside class="map-modal-sidebar">
        <div>
          <h3 class="ruled-title" style="margin-bottom: var(--space-xs)">Intensidad de zonas de calor</h3>
          <div class="map-legend" style="margin-top: 0">
            <span class="legend-item"><span class="legend-swatch swatch--heat-low"></span>1 alerta</span>
            <span class="legend-item"><span class="legend-swatch swatch--heat-mid"></span>2–3 alertas</span>
            <span class="legend-item"><span class="legend-swatch swatch--heat-high"></span>4+ alertas</span>
            <span class="legend-item"><span class="legend-swatch swatch--kmz"></span>Polígonos KMZ</span>
          </div>
        </div>

        <div>
          <h3 class="ruled-title" style="margin-bottom: var(--space-xs)">Prioridad de indicadores</h3>
          <div class="map-legend" style="margin-top: 0">
            <span class="legend-item"><span class="legend-swatch swatch--critica"></span>Crítica</span>
            <span class="legend-item"><span class="legend-swatch swatch--alta"></span>Alta</span>
            <span class="legend-item"><span class="legend-swatch swatch--media"></span>Media</span>
            <span class="legend-item"><span class="legend-swatch swatch--baja"></span>Baja</span>
          </div>
        </div>

        <div>
          <h3 class="ruled-title" style="margin-bottom: var(--space-xs)">Lugares con alertas activas</h3>
          <p class="ruled-desc" style="margin-bottom: var(--space-xs)">Haz clic en una alerta para geolocalizarla en el mapa.</p>
          <div id="map-modal-alerts-list" class="ruled-list map-alerts-scroll"></div>
        </div>
      </aside>
    </div>
  </dialog>

  <!-- MODAL DE DETALLE DE ALERTA -->
  <dialog id="detail-dialog" class="native-dialog native-dialog--detail" aria-labelledby="detail-title">
    <header class="dialog-header">
      <h2 id="detail-title" class="panel-title">Detalle de alerta</h2>
      <button id="btn-close-detail" type="button" class="btn-line">Cerrar</button>
    </header>
    <div id="detail-body" class="dialog-body"></div>
  </dialog>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="/assets/js/panel.js" defer></script>
</body>
</html>
