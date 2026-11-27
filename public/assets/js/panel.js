(() => {
  "use strict";

  document.documentElement.classList.add("js-ready");

  const panelType = document.body.dataset.panel || "cra"; // "cra" | "empresa"
  const PAGE_SIZE = 10;

  // Catálogo oficial de subecosistemas del Atlántico (GPS reales)
  const ALL_ZONES = [
    { id: "zone_mallorquin", name: "Ciénaga de Mallorquín", lat: 11.0458, lng: -74.8461 },
    { id: "zone_balboa", name: "Puerto Colombia", lat: 10.9878, lng: -74.9547 },
    { id: "zone_tubara", name: "Tubará", lat: 10.8753, lng: -74.9794 },
    { id: "zone_juan_acosta", name: "Juan de Acosta", lat: 10.8286, lng: -75.0353 },
    { id: "zone_totumo", name: "Ciénaga del Totumo", lat: 10.7452, lng: -75.2414 },
  ];

  const PAID_EMPRESA_IDS = new Set(["zone_mallorquin", "zone_balboa"]);
  const SEV_RANK = { "CRÍTICA": 4, ALTA: 3, MEDIA: 2, BAJA: 1 };

  let allReports = [];
  let subscribers = [];
  let kmzGeoJson = null;

  const state = {
    view: "dashboard",
    search: "",
    severityFilter: "", // "" | "CRÍTICA" | "ALTA" | "MEDIA" | "BAJA"
    currentPage: 1,
    mapFilterSev: "",
    mapFilterZone: "",
    showKmz: true,
  };

  // Navegación
  const navButtons = document.querySelectorAll(".nav-item[data-view]");
  const viewPanels = document.querySelectorAll(".view-panel");
  const sidebar = document.getElementById("sidebar");
  const menuToggle = document.getElementById("menu-toggle");

  function switchView(viewName) {
    state.view = viewName;
    navButtons.forEach((btn) => {
      if (btn.dataset.view === viewName) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
    viewPanels.forEach((panel) => {
      panel.dataset.active = String(panel.id === `view-${viewName}`);
    });
    sidebar.dataset.open = "false";
    menuToggle.setAttribute("aria-expanded", "false");
    if (viewName === "dashboard" && dashMap) {
      window.setTimeout(() => dashMap.invalidateSize(), 120);
    }
  }

  navButtons.forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  document.querySelectorAll("[data-jump-view]").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.jumpView));
  });

  menuToggle.addEventListener("click", () => {
    const open = sidebar.dataset.open === "true";
    sidebar.dataset.open = String(!open);
    menuToggle.setAttribute("aria-expanded", String(!open));
  });

  // Normalización de reportes
  function normSeverity(report) {
    const raw = (report?.cra_technical_report?.nivel_severidad || "MEDIA").toUpperCase();
    if (raw.includes("CRIT") || raw.includes("CRÍT")) return "CRÍTICA";
    if (raw.includes("ALT")) return "ALTA";
    if (raw.includes("BAJ")) return "BAJA";
    return "MEDIA";
  }

  function sevFromScore(score) {
    if (score >= 85) return { sev: "CRÍTICA", label: "Crítico" };
    if (score >= 70) return { sev: "ALTA", label: "Alto" };
    if (score >= 40) return { sev: "MEDIA", label: "Medio" };
    if (score > 0) return { sev: "BAJA", label: "Bajo" };
    return { sev: "BAJA", label: "Estable" };
  }

  function cleanText(str) {
    return String(str || "")
      .replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\s]+/gu, "")
      .trim();
  }

  function resolveZoneId(r) {
    const zId = String(r?.location?.zone_id || "").toLowerCase();
    const zTitle = String(r?.location?.zone_title || "").toLowerCase();
    if (zId === "zone_mallorquin" || zTitle.includes("mallorqu")) return "zone_mallorquin";
    if (zId === "zone_balboa" || zTitle.includes("puerto colombia") || zTitle.includes("balboa") || zTitle.includes("salgar")) return "zone_balboa";
    if (zId === "zone_tubara" || zTitle.includes("tubar")) return "zone_tubara";
    if (zId === "zone_juan_acosta" || zTitle.includes("juan de acosta")) return "zone_juan_acosta";
    if (zId === "zone_totumo" || zTitle.includes("totumo")) return "zone_totumo";
    return zId || "zone_mallorquin";
  }

  function formatReport(r) {
    const tech = r.cra_technical_report || {};
    const zoneId = resolveZoneId(r);
    const zoneDef = ALL_ZONES.find((z) => z.id === zoneId) || ALL_ZONES[0];
    const radicado = r.id || "Sin radicado";
    const zona = r.location?.zone_title || zoneDef.name;
    const anomalia =
      cleanText(r.incident?.category_title) ||
      cleanText(tech.subcategoria_tecnica_cra) ||
      "Incidente ambiental";
    const sev = normSeverity(r);
    const riesgo = Number(tech.indice_riesgo_ambiental ?? 0);
    const prioridad = `${sev} (Riesgo ${riesgo}/100)`;
    const informe =
      cleanText(tech.titulo_hallazgo) ||
      cleanText(r.incident?.citizen_description) ||
      `Incidente de ${anomalia} reportado en ${zona}.`;

    const lat = Number.isFinite(Number(r.location?.lat)) ? Number(r.location.lat) : zoneDef.lat;
    const lng = Number.isFinite(Number(r.location?.lng)) ? Number(r.location.lng) : zoneDef.lng;

    return {
      raw: r,
      radicado,
      zoneId,
      zona,
      anomalia,
      sev,
      riesgo,
      prioridad,
      informe,
      lat,
      lng,
      imageUrl: r.incident?.image_url || "",
    };
  }

  function getActiveZones() {
    return panelType === "empresa"
      ? ALL_ZONES.filter((z) => PAID_EMPRESA_IDS.has(z.id))
      : ALL_ZONES;
  }

  function getTenantReports() {
    const formatted = allReports.map(formatReport);
    if (panelType === "empresa") {
      return formatted.filter((f) => PAID_EMPRESA_IDS.has(f.zoneId));
    }
    return formatted;
  }

  function getFilteredReports(ignoreSeverity = false) {
    return getTenantReports().filter((f) => {
      if (!ignoreSeverity && state.severityFilter && f.sev !== state.severityFilter) return false;
      if (state.search) {
        const hay = `${f.radicado} ${f.zona} ${f.anomalia} ${f.prioridad} ${f.informe}`.toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    });
  }

  // =========================================================================
  // LEAFLET MAPA REAL (KMZ + ZONAS DE CALOR DINÁMICAS + CLUSTERING + FLYTO)
  // =========================================================================
  let dashMap = null;
  let dashHeatLayer = null;
  let dashPinLayer = null;
  let dashKmzLayer = null;

  let modalMap = null;
  let modalHeatLayer = null;
  let modalPinLayer = null;
  let modalKmzLayer = null;
  let modalPulseLayer = null;

  function initLeafletInstance(containerId, interactive) {
    if (typeof L === "undefined") return null;
    const map = L.map(containerId, {
      center: [10.94, -74.96],
      zoom: interactive ? 10 : 9,
      zoomControl: interactive,
      dragging: interactive,
      scrollWheelZoom: interactive,
      doubleClickZoom: interactive,
      boxZoom: interactive,
      touchZoom: interactive,
      attributionControl: false,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 18,
      subdomains: "abcd",
    }).addTo(map);

    return map;
  }

  function renderKmzInto(map, existingLayer) {
    if (!map || !kmzGeoJson) return existingLayer;
    if (existingLayer) map.removeLayer(existingLayer);
    if (!state.showKmz) return null;

    return L.geoJSON(kmzGeoJson, {
      style: {
        color: "#5B8F80",
        weight: 1,
        opacity: 0.75,
        fillColor: "#8DA28B",
        fillOpacity: 0.22,
      },
      interactive: false,
    }).addTo(map);
  }

  // Nueva mecánica de Zonas de Calor: entre más alertas en una zona, más oscuro/intenso el color
  function renderHeatAndClusters(map, heatGroup, pinGroup, items, allowClickDetail) {
    if (!map || !heatGroup || !pinGroup) return;
    heatGroup.clearLayers();
    pinGroup.clearLayers();
    if (!items.length) return;

    // 1. Calcular densidad por proximidad geográfica (~3km) para oscurecer el calor
    const densityMap = new Map();
    items.forEach((a) => {
      let count = 0;
      items.forEach((b) => {
        const d = Math.hypot(a.lat - b.lat, a.lng - b.lng);
        if (d < 0.03) count += 1;
      });
      densityMap.set(a.radicado, count);
    });

    items.forEach((f) => {
      const density = densityMap.get(f.radicado) || 1;
      // Escala progresiva: 1 alerta = ámbar suave; 2-3 = naranja intenso; 4+ = carmesí oscuro
      let fill = "#D99B26";
      let opacity = 0.26;
      let radius = 2600;
      if (density >= 4 || f.sev === "CRÍTICA") {
        fill = "#8F1111";
        opacity = Math.min(0.68, 0.36 + density * 0.07);
        radius = 3400;
      } else if (density >= 2 || f.sev === "ALTA") {
        fill = "#C94A1A";
        opacity = Math.min(0.55, 0.30 + density * 0.07);
        radius = 3000;
      }
      L.circle([f.lat, f.lng], {
        radius,
        stroke: false,
        fillColor: fill,
        fillOpacity: opacity,
        interactive: false,
      }).addTo(heatGroup);
    });

    // 2. Clustering dinámico en pantalla según nivel de zoom actual
    const zoom = map.getZoom();
    const clusterThresholdPx = zoom >= 13 ? 16 : zoom >= 11 ? 34 : 54;
    const clusters = [];

    items.forEach((f) => {
      const pt = map.latLngToContainerPoint([f.lat, f.lng]);
      let found = null;
      for (const c of clusters) {
        if (Math.hypot(c.px - pt.x, c.py - pt.y) <= clusterThresholdPx) {
          found = c;
          break;
        }
      }
      if (found) {
        found.items.push(f);
        found.latSum += f.lat;
        found.lngSum += f.lng;
        if (SEV_RANK[f.sev] > SEV_RANK[found.topSev]) found.topSev = f.sev;
      } else {
        clusters.push({
          px: pt.x,
          py: pt.y,
          latSum: f.lat,
          lngSum: f.lng,
          topSev: f.sev,
          items: [f],
        });
      }
    });

    // 3. Regla anti-solapamiento: ocultar etiqueta si otro indicador está a < 72px en pantalla
    const LABEL_MIN_DIST_PX = 72;
    const screenPts = clusters.map((c) => {
      const lat = c.latSum / c.items.length;
      const lng = c.lngSum / c.items.length;
      const p = map.latLngToContainerPoint([lat, lng]);
      return { c, lat, lng, x: p.x, y: p.y };
    });

    screenPts.forEach((entry, idx) => {
      let tooClose = false;
      for (let j = 0; j < screenPts.length; j++) {
        if (idx === j) continue;
        if (Math.hypot(entry.x - screenPts[j].x, entry.y - screenPts[j].y) < LABEL_MIN_DIST_PX) {
          tooClose = true;
          break;
        }
      }

      const labelText = entry.c.topSev.charAt(0) + entry.c.topSev.slice(1).toLowerCase();
      const countText = entry.c.items.length > 1 ? String(entry.c.items.length) : "!";
      const icon = L.divIcon({
        className: "",
        html: `
          <div class="mokana-pin-wrap">
            <span class="mokana-pin-dot mokana-pin-dot--${entry.c.topSev}">${countText}</span>
            <span class="mokana-pin-label ${tooClose ? "mokana-pin-label--hidden" : ""}">${labelText}</span>
          </div>
        `,
        iconSize: [0, 0],
      });

      const marker = L.marker([entry.lat, entry.lng], { icon }).addTo(pinGroup);
      if (allowClickDetail) {
        marker.on("click", () => {
          if (entry.c.items.length === 1) {
            openReportDetail(entry.c.items[0]);
          } else {
            map.flyTo([entry.lat, entry.lng], Math.min(15, map.getZoom() + 2), { duration: 0.7 });
          }
        });
      }
    });
  }

  function getModalMapReports() {
    return getTenantReports().filter((f) => {
      if (state.mapFilterSev && f.sev !== state.mapFilterSev) return false;
      if (state.mapFilterZone && f.zoneId !== state.mapFilterZone) return false;
      return true;
    });
  }

  function refreshMaps() {
    if (dashMap) {
      dashKmzLayer = renderKmzInto(dashMap, dashKmzLayer);
      renderHeatAndClusters(dashMap, dashHeatLayer, dashPinLayer, getTenantReports(), false);
    }
    if (modalMap && mapDialog.open) {
      modalKmzLayer = renderKmzInto(modalMap, modalKmzLayer);
      renderHeatAndClusters(modalMap, modalHeatLayer, modalPinLayer, getModalMapReports(), true);
    }
  }

  function setupMaps() {
    dashMap = initLeafletInstance("dash-map-viewport", false);
    if (dashMap) {
      dashHeatLayer = L.layerGroup().addTo(dashMap);
      dashPinLayer = L.layerGroup().addTo(dashMap);
    }
  }

  // Modal Completo del Mapa + Filtros + FlyTo Geolocalización
  const mapDialog = document.getElementById("map-dialog");
  const dashMapEl = document.getElementById("dash-map-viewport");

  function openMapModal() {
    mapDialog.showModal();
    if (!modalMap) {
      modalMap = initLeafletInstance("modal-map-viewport", true);
      if (modalMap) {
        modalHeatLayer = L.layerGroup().addTo(modalMap);
        modalPinLayer = L.layerGroup().addTo(modalMap);
        modalPulseLayer = L.layerGroup().addTo(modalMap);
        modalMap.on("zoomend moveend", () => {
          renderHeatAndClusters(modalMap, modalHeatLayer, modalPinLayer, getModalMapReports(), true);
        });
      }
    }
    window.setTimeout(() => {
      if (modalMap) modalMap.invalidateSize();
      refreshMaps();
      renderMapModalSidebar();
    }, 100);
  }

  dashMapEl.addEventListener("click", openMapModal);
  dashMapEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openMapModal();
    }
  });
  document.getElementById("btn-open-map-modal").addEventListener("click", openMapModal);
  document.getElementById("btn-minimize-map").addEventListener("click", () => mapDialog.close());
  mapDialog.addEventListener("click", (e) => {
    if (e.target === mapDialog) mapDialog.close();
  });

  // Filtros dentro del Modal del Mapa
  document.getElementById("map-filter-sev").addEventListener("change", (e) => {
    state.mapFilterSev = e.target.value;
    refreshMaps();
    renderMapModalSidebar();
  });

  document.getElementById("map-filter-zone").addEventListener("change", (e) => {
    state.mapFilterZone = e.target.value;
    refreshMaps();
    renderMapModalSidebar();
  });

  const btnToggleKmz = document.getElementById("btn-toggle-kmz");
  btnToggleKmz.addEventListener("click", () => {
    state.showKmz = !state.showKmz;
    btnToggleKmz.setAttribute("aria-pressed", String(state.showKmz));
    refreshMaps();
  });

  // Animación de geolocalización (flyTo + pulso) al hacer clic en una alerta del listado
  function geolocateAlertOnModalMap(f) {
    if (!modalMap) return;
    modalMap.flyTo([f.lat, f.lng], 14, { duration: 1.0 });
    if (modalPulseLayer) {
      modalPulseLayer.clearLayers();
      const pulseIcon = L.divIcon({
        className: "",
        html: `<div class="geo-pulse-ring"></div>`,
        iconSize: [0, 0],
      });
      L.marker([f.lat, f.lng], { icon: pulseIcon, interactive: false }).addTo(modalPulseLayer);
      window.setTimeout(() => modalPulseLayer.clearLayers(), 2000);
    }
  }

  function renderMapModalSidebar() {
    const list = document.getElementById("map-modal-alerts-list");
    if (!list) return;
    const items = getModalMapReports();
    list.innerHTML = "";

    if (!items.length) {
      list.innerHTML = `<span class="ruled-desc">Sin alertas activas para este filtro.</span>`;
      return;
    }

    items.forEach((f) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-alert-btn";
      btn.innerHTML = `
        <span class="ruled-copy">
          <span class="ruled-title">${f.zona} (${f.radicado})</span>
          <span class="ruled-desc">${f.anomalia}</span>
        </span>
        <span class="badge badge--${f.sev}">${f.sev}</span>
      `;
      btn.addEventListener("click", () => geolocateAlertOnModalMap(f));
      list.appendChild(btn);
    });
  }

  // Modal de Detalle limpio (Radicado, Zona, Anomalía, Prioridad, Informe)
  const detailDialog = document.getElementById("detail-dialog");
  document.getElementById("btn-close-detail").addEventListener("click", () => detailDialog.close());
  detailDialog.addEventListener("click", (e) => {
    if (e.target === detailDialog) detailDialog.close();
  });

  function openReportDetail(f) {
    document.getElementById("detail-title").textContent = `Radicado: ${f.radicado}`;
    const body = document.getElementById("detail-body");
    const photoHtml = f.imageUrl
      ? `<img class="detail-photo" src="${f.imageUrl}" alt="Evidencia de ${f.radicado}" onerror="this.style.display='none'" />`
      : "";

    body.innerHTML = `
      ${photoHtml}
      <div class="ruled-list">
        <div class="ruled-row"><span class="ruled-title">Radicado</span><span class="num">${f.radicado}</span></div>
        <div class="ruled-row"><span class="ruled-title">Zona</span><span>${f.zona}</span></div>
        <div class="ruled-row"><span class="ruled-title">Anomalía</span><span>${f.anomalia}</span></div>
        <div class="ruled-row"><span class="ruled-title">Prioridad</span><span class="badge badge--${f.sev}">${f.prioridad}</span></div>
        <div class="ruled-row">
          <span class="ruled-copy">
            <span class="ruled-title">Informe</span>
            <span class="ruled-desc">${f.informe}</span>
          </span>
        </div>
      </div>
    `;
    detailDialog.showModal();
  }

  // Renderizado de filas (Últimas 10 y Gestión de Alertas)
  function renderRowsInto(items, tbodyId, emptyId, wrapId) {
    const tbody = document.getElementById(tbodyId);
    const emptyBox = document.getElementById(emptyId);
    const wrap = document.getElementById(wrapId);
    if (!tbody || !emptyBox || !wrap) return;

    if (!items.length) {
      wrap.style.display = "none";
      emptyBox.style.display = "grid";
      return;
    }

    emptyBox.style.display = "none";
    wrap.style.display = "block";
    tbody.innerHTML = "";

    items.forEach((f) => {
      const tr = document.createElement("tr");
      if (f.sev === "CRÍTICA") tr.className = "row--critical";
      else if (f.sev === "ALTA") tr.className = "row--high";

      tr.innerHTML = `
        <td class="num">${f.radicado}</td>
        <td><strong>${f.zona}</strong></td>
        <td>${f.anomalia}</td>
        <td><span class="badge badge--${f.sev}">${f.prioridad}</span></td>
        <td>${f.informe}</td>
        <td><button type="button" class="btn-line">Ver detalle</button></td>
      `;
      tr.querySelector("button").addEventListener("click", () => openReportDetail(f));
      tbody.appendChild(tr);
    });
  }

  // Dashboard: Ecosistema General + Subecosistemas (Sistema de Promedio de Riesgo Máximo)
  function renderDashboard() {
    const items = getTenantReports();
    const zones = getActiveZones();
    const subList = document.getElementById("subecosystems-list");
    subList.innerHTML = "";

    const affectedMaxRisks = [];

    zones.forEach((z) => {
      const zAlerts = items.filter((f) => f.zoneId === z.id);
      const maxRisk = zAlerts.length ? Math.max(...zAlerts.map((a) => a.riesgo)) : 0;
      if (zAlerts.length > 0) affectedMaxRisks.push(maxRisk);
      const level = sevFromScore(maxRisk);

      const row = document.createElement("div");
      row.className = "subeco-row";
      row.innerHTML = `
        <span class="subeco-name">${z.name}</span>
        <span class="subeco-stats">
          <span class="ruled-desc num">${zAlerts.length} al.</span>
          <span class="badge badge--${level.sev}">${maxRisk}/100</span>
        </span>
      `;
      subList.appendChild(row);
    });

    // Promedio de los riesgos máximos de las zonas afectadas (0–100)
    const generalAvgRisk = affectedMaxRisks.length
      ? Math.round(affectedMaxRisks.reduce((acc, v) => acc + v, 0) / affectedMaxRisks.length)
      : 0;
    const generalLevel = sevFromScore(generalAvgRisk);

    document.getElementById("dash-active-count").innerHTML = `${items.length}<span class="u">activas</span>`;
    document.getElementById("dash-avg-risk").innerHTML = `${generalAvgRisk}<span class="u">/100</span>`;
    document.getElementById("nav-alert-count").textContent = String(items.length);

    const ecoBadge = document.getElementById("dash-eco-badge");
    ecoBadge.className = `badge badge--${generalLevel.sev}`;
    ecoBadge.textContent = generalLevel.label;

    const latestTen = getFilteredReports(true).slice(0, 10);
    renderRowsInto(latestTen, "dash-alerts-tbody", "dash-alerts-empty", "dash-alerts-table-wrap");
  }

  // Gestión de Alertas: Filtros por Prioridad + Paginado Exclusivo
  const escCards = document.querySelectorAll(".esc-card[data-sev]");
  const sevFilterBtns = document.querySelectorAll(".sev-filter-btn[data-sev-filter]");

  function setSeverityFilter(sev) {
    state.severityFilter = state.severityFilter === sev && sev !== "" ? "" : sev;
    state.currentPage = 1;
    renderAlertas();
  }

  escCards.forEach((card) => card.addEventListener("click", () => setSeverityFilter(card.dataset.sev)));
  sevFilterBtns.forEach((btn) => btn.addEventListener("click", () => {
    state.severityFilter = btn.dataset.sevFilter;
    state.currentPage = 1;
    renderAlertas();
  }));

  function renderAlertas() {
    const base = getTenantReports();
    const counts = { "CRÍTICA": 0, ALTA: 0, MEDIA: 0, BAJA: 0 };
    base.forEach((f) => {
      if (counts[f.sev] !== undefined) counts[f.sev] += 1;
    });

    document.getElementById("esc-cnt-critica").textContent = String(counts["CRÍTICA"]);
    document.getElementById("esc-cnt-alta").textContent = String(counts.ALTA);
    document.getElementById("esc-cnt-media").textContent = String(counts.MEDIA);
    document.getElementById("esc-cnt-baja").textContent = String(counts.BAJA);

    escCards.forEach((c) => c.setAttribute("aria-pressed", String(state.severityFilter === c.dataset.sev)));
    sevFilterBtns.forEach((b) => b.setAttribute("aria-pressed", String(state.severityFilter === b.dataset.sevFilter)));

    const filtered = getFilteredReports(false);
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (state.currentPage > totalPages) state.currentPage = totalPages;

    const startIdx = (state.currentPage - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(startIdx, startIdx + PAGE_SIZE);

    document.getElementById("alerts-count-label").textContent = `${total} registros`;
    renderRowsInto(pageItems, "alerts-tbody", "alerts-empty", "alerts-table-wrap");

    const pagBar = document.getElementById("alerts-pagination");
    const pagInfo = document.getElementById("pagination-info");
    const pagControls = document.getElementById("pagination-controls");

    if (total === 0) {
      pagBar.style.display = "none";
      return;
    }

    pagBar.style.display = "flex";
    const from = startIdx + 1;
    const to = Math.min(total, startIdx + pageItems.length);
    pagInfo.textContent = `Mostrando ${from}–${to} de ${total} alertas`;
    pagControls.innerHTML = "";

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "page-btn";
    prevBtn.textContent = "Anterior";
    prevBtn.disabled = state.currentPage <= 1;
    prevBtn.addEventListener("click", () => {
      state.currentPage -= 1;
      renderAlertas();
    });
    pagControls.appendChild(prevBtn);

    for (let p = 1; p <= totalPages; p++) {
      const pBtn = document.createElement("button");
      pBtn.type = "button";
      pBtn.className = "page-btn";
      pBtn.textContent = String(p);
      if (p === state.currentPage) pBtn.setAttribute("aria-current", "page");
      pBtn.addEventListener("click", () => {
        state.currentPage = p;
        renderAlertas();
      });
      pagControls.appendChild(pBtn);
    }

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "page-btn";
    nextBtn.textContent = "Siguiente";
    nextBtn.disabled = state.currentPage >= totalPages;
    nextBtn.addEventListener("click", () => {
      state.currentPage += 1;
      renderAlertas();
    });
    pagControls.appendChild(nextBtn);
  }

  function renderSubscribers() {
    const tbody = document.getElementById("tenants-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!subscribers.length) {
      tbody.innerHTML = `<tr><td colspan="5">Sin suscriptores cargados desde /api/subscribers.</td></tr>`;
      return;
    }
    subscribers.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${s.organization || s.name}</strong></td>
        <td>${s.type || "EMPRESA"}</td>
        <td>${s.plan || "PRO"}</td>
        <td>${Array.isArray(s.zones) ? s.zones.join(", ") : "Todas"}</td>
        <td><span class="badge ${s.active ? "badge--BAJA" : "badge--MEDIA"}">${s.active ? "Activo" : "Inactivo"}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Exportación conectada al nuevo endpoint oficial /api/reports/export?format=csv|geojson|json
  function triggerOfficialExport(format) {
    if (panelType === "cra") {
      window.location.href = `/api/reports/export?format=${format}`;
      return;
    }
    // Para Empresa: exporta solo sus sectores pagados (Mallorquín y Puerto Colombia)
    const items = getTenantReports();
    if (format === "csv") {
      const header = ["Radicado", "Zona", "Anomalia", "Prioridad", "Informe"];
      const rows = items.map((f) => [f.radicado, `"${f.zona}"`, `"${f.anomalia}"`, `"${f.prioridad}"`, `"${f.informe.replace(/"/g, "'")}"`]);
      downloadLocal(`mokana-empresa-${format}.csv`, [header.join(","), ...rows.map((r) => r.join(","))].join("\n"), "text/csv;charset=utf-8;");
    } else if (format === "geojson") {
      const fc = {
        type: "FeatureCollection",
        features: items.map((f) => ({
          type: "Feature",
          properties: { radicado: f.radicado, zona: f.zona, anomalia: f.anomalia, prioridad: f.prioridad, informe: f.informe },
          geometry: { type: "Point", coordinates: [f.lng, f.lat] },
        })),
      };
      downloadLocal("mokana-empresa-alertas.geojson", JSON.stringify(fc, null, 2), "application/geo+json;charset=utf-8;");
    } else {
      downloadLocal("mokana-empresa-alertas.json", JSON.stringify(items.map((f) => f.raw), null, 2), "application/json;charset=utf-8;");
    }
  }

  function downloadLocal(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  document.getElementById("exp-csv").addEventListener("click", () => triggerOfficialExport("csv"));
  document.getElementById("exp-geojson").addEventListener("click", () => triggerOfficialExport("geojson"));
  const expJsonBtn = document.getElementById("exp-json");
  if (expJsonBtn) expJsonBtn.addEventListener("click", () => triggerOfficialExport("json"));
  document.getElementById("exp-pdf").addEventListener("click", () => window.print());

  document.getElementById("search-global").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    state.currentPage = 1;
    renderAll();
  });

  const netChip = document.getElementById("net-status");
  const netLabel = document.getElementById("net-label");
  function updateNetwork() {
    const offline = !navigator.onLine;
    netChip.dataset.offline = String(offline);
    netLabel.textContent = offline ? "Sin conexión" : "En línea";
  }
  window.addEventListener("online", updateNetwork);
  window.addEventListener("offline", updateNetwork);

  function renderAll() {
    renderDashboard();
    renderAlertas();
    renderSubscribers();
    refreshMaps();
    renderMapModalSidebar();
    updateNetwork();
  }

  async function loadKmzGeoJson() {
    try {
      const res = await fetch("/assets/data/prioridades_atlantico.geojson");
      if (res.ok) {
        kmzGeoJson = await res.json();
        refreshMaps();
      }
    } catch {
      // Fallback sin capa KMZ si falla
    }
  }

  async function loadFromBotApi() {
    try {
      const res = await fetch("/api/reports", { headers: { Accept: "application/json" } });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.reports)) allReports = data.reports;
      }
    } catch {
      // Mantiene estado limpio sin red
    }

    if (panelType === "cra") {
      try {
        const sRes = await fetch("/api/subscribers", { headers: { Accept: "application/json" } });
        if (sRes.ok) {
          const sData = await sRes.json();
          subscribers = Array.isArray(sData) ? sData : (sData.subscribers || []);
        }
      } catch {
        // Ignora sin red
      }
    }
    renderAll();
  }

  function connectSSE() {
    if (typeof EventSource === "undefined") return;
    try {
      const es = new EventSource("/api/events/stream");
      es.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.event === "report.created" && payload.data) {
            if (!allReports.some((r) => r.id === payload.data.id)) allReports.unshift(payload.data);
            renderAll();
          } else if (payload.event === "report.updated" && payload.data) {
            const idx = allReports.findIndex((r) => r.id === payload.data.id);
            if (idx !== -1) allReports[idx] = payload.data;
            else allReports.unshift(payload.data);
            renderAll();
          }
        } catch {
          // Ignora heartbeats
        }
      };
    } catch {
      // Sin soporte SSE
    }
  }

  const refreshBtn = document.getElementById("btn-refresh-api");
  if (refreshBtn) refreshBtn.addEventListener("click", () => loadFromBotApi());

  setupMaps();
  renderAll();
  loadKmzGeoJson();
  loadFromBotApi();
  connectSSE();
})();
