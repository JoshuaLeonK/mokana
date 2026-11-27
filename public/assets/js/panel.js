(() => {
  "use strict";

  document.documentElement.classList.add("js-ready");

  const panelType = document.body.dataset.panel || "cra"; // "cra" | "empresa"
  const SUBSCRIBER_ZONES = new Set(["zone_mallorquin", "zone_balboa"]);
  const SUBSCRIBER_SEVERITIES = new Set(["CRÍTICA", "ALTA"]);

  // Map percentage coordinates for the 5 official C.R.A Atlántico zones on relieve.jpg
  const ZONE_COORDS = {
    zone_mallorquin: { x: 78, y: 21, label: "Ciénaga de Mallorquín" },
    zone_balboa: { x: 64, y: 38, label: "Puerto Velero / Balboa" },
    zone_tubara: { x: 56, y: 45, label: "Tubarà / Playa Mendoza" },
    zone_juan_acosta: { x: 46, y: 58, label: "Juan de Acosta" },
    zone_totumo: { x: 32, y: 74, label: "Ciénaga del Totumo" },
  };

  // Zero hardcoded dummy alerts — populated strictly from live Bot API + SSE
  let allReports = [];
  let subscribers = [];

  const state = {
    view: "dashboard",
    search: "",
    severityFilter: null, // "CRÍTICA" | "ALTA" | "MEDIA" | "BAJA" | null
    sseConnected: false,
    lastBotEventAt: null,
  };

  // DOM helpers
  const contentEl = document.getElementById("main-content");
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
    // Pure full-bleed map mode for "Mapa en vivo" (zero padding, zero extra UI)
    contentEl.dataset.fullbleed = String(viewName === "mapa");
    sidebar.dataset.open = "false";
    menuToggle.setAttribute("aria-expanded", "false");
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

  // Normalize severity string from Bot API (Gemini 2.5 Flash)
  function normSeverity(report) {
    const raw = (report?.cra_technical_report?.nivel_severidad || "MEDIA").toUpperCase();
    if (raw.includes("CRIT") || raw.includes("CRÍT")) return "CRÍTICA";
    if (raw.includes("ALT")) return "ALTA";
    if (raw.includes("BAJ")) return "BAJA";
    return "MEDIA";
  }

  function getCoords(report) {
    const zId = report?.location?.zone_id || "zone_mallorquin";
    if (ZONE_COORDS[zId]) return ZONE_COORDS[zId];
    return { x: 64, y: 40, label: report?.location?.zone_title || "Atlántico" };
  }

  // Filter reports by Tenant (CRA sees all; Empresa sees contracted zones + ALTA/CRÍTICA)
  function getTenantReports() {
    return allReports.filter((r) => {
      if (panelType === "empresa") {
        const zId = r?.location?.zone_id || "";
        const sev = normSeverity(r);
        if (!SUBSCRIBER_ZONES.has(zId)) return false;
        if (!SUBSCRIBER_SEVERITIES.has(sev)) return false;
      }
      return true;
    });
  }

  function getFilteredReports(ignoreSeverity = false) {
    return getTenantReports().filter((r) => {
      const sev = normSeverity(r);
      if (!ignoreSeverity && state.severityFilter && sev !== state.severityFilter) return false;
      if (state.search) {
        const hay = [
          r.id,
          r.location?.zone_title,
          r.incident?.category_title,
          r.incident?.citizen_description,
          r.cra_technical_report?.titulo_hallazgo,
          sev,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    });
  }

  // Pan & Zoom controller
  function attachPanZoom(viewportId, stageId, zoomInId, zoomOutId, resetId) {
    const viewport = document.getElementById(viewportId);
    const stage = document.getElementById(stageId);
    if (!viewport || !stage) return { reset: () => {} };

    let scale = 1;
    let tx = 0;
    let ty = 0;
    let dragging = false;
    let sx = 0;
    let sy = 0;

    const zIn = zoomInId ? document.getElementById(zoomInId) : null;
    const zOut = zoomOutId ? document.getElementById(zoomOutId) : null;
    const zReset = resetId ? document.getElementById(resetId) : null;

    function apply() {
      const mx = (viewport.clientWidth * (scale - 1)) / 2;
      const my = (viewport.clientHeight * (scale - 1)) / 2;
      tx = Math.max(-mx, Math.min(mx, tx));
      ty = Math.max(-my, Math.min(my, ty));
      stage.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      if (zReset) zReset.textContent = `${Math.round(scale * 100)}%`;
    }

    function setZoom(next) {
      scale = Math.max(1, Math.min(3, Number(next.toFixed(2))));
      if (scale === 1) {
        tx = 0;
        ty = 0;
      }
      apply();
    }

    if (zIn) zIn.addEventListener("click", () => setZoom(scale + 0.35));
    if (zOut) zOut.addEventListener("click", () => setZoom(scale - 0.35));
    if (zReset) zReset.addEventListener("click", () => setZoom(1));

    viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      setZoom(scale + (e.deltaY < 0 ? 0.2 : -0.2));
    }, { passive: false });

    viewport.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".map-pin") || scale <= 1) return;
      dragging = true;
      sx = e.clientX - tx;
      sy = e.clientY - ty;
      stage.dataset.dragging = "true";
      viewport.setPointerCapture(e.pointerId);
    });

    viewport.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      tx = e.clientX - sx;
      ty = e.clientY - sy;
      apply();
    });

    const end = () => {
      dragging = false;
      stage.dataset.dragging = "false";
    };
    viewport.addEventListener("pointerup", end);
    viewport.addEventListener("pointercancel", end);

    return { reset: () => setZoom(1) };
  }

  attachPanZoom("dash-map-viewport", "dash-map-stage", "zoom-in", "zoom-out", "zoom-reset");
  attachPanZoom("pure-map-viewport", "pure-map-stage", null, null, null);
  const dialogPan = attachPanZoom("dialog-map-viewport", "dialog-map-stage", "dialog-zoom-in", "dialog-zoom-out", "dialog-zoom-reset");

  // Maximize / Minimize Map Dialog
  const mapDialog = document.getElementById("map-dialog");
  document.getElementById("btn-maximize-map").addEventListener("click", () => {
    dialogPan.reset();
    renderAllPins();
    mapDialog.showModal();
  });
  document.getElementById("btn-minimize-map").addEventListener("click", () => mapDialog.close());
  mapDialog.addEventListener("click", (e) => {
    if (e.target === mapDialog) mapDialog.close();
  });

  // Read-only AI Technical Report Dialog
  const detailDialog = document.getElementById("detail-dialog");
  document.getElementById("btn-close-detail").addEventListener("click", () => detailDialog.close());
  detailDialog.addEventListener("click", (e) => {
    if (e.target === detailDialog) detailDialog.close();
  });

  function openReportDetail(r) {
    const tech = r.cra_technical_report || {};
    const sev = normSeverity(r);
    document.getElementById("detail-title").textContent = `${r.id} (${sev})`;
    const body = document.getElementById("detail-body");
    const species = Array.isArray(tech.especies_mangle_riesgo) ? tech.especies_mangle_riesgo.join(", ") : "Sin especificar";
    const photoHtml = r.incident?.image_url
      ? `<img class="detail-photo" src="${r.incident.image_url}" alt="Evidencia del reporte" />`
      : "";

    body.innerHTML = `
      ${photoHtml}
      <div class="ruled-list">
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Hallazgo técnico IA</span><span class="ruled-desc">${tech.titulo_hallazgo || r.incident?.citizen_description || "Sin descripción"}</span></span>
          <span class="badge badge--${sev}">${sev}</span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Sector</span><span class="ruled-desc">${r.location?.zone_title || r.location?.zone_id || "Atlántico"}</span></span>
          <span class="num">${tech.indice_riesgo_ambiental ?? 0}<span class="u">/100 riesgo</span></span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Confianza Agente IA (Gemini 2.5 Flash)</span><span class="ruled-desc">${tech.coherencia_foto_descripcion || "Evaluado automáticamente por el bot"}</span></span>
          <span class="num">${tech.puntaje_confianza_ia ?? 0}<span class="u">%</span></span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Subcategoría C.R.A</span><span class="ruled-desc">${tech.subcategoria_tecnica_cra || r.incident?.category_title || "General"}</span></span>
          <span class="ruled-desc">SLA ${tech.sla_tiempo_respuesta_horas ?? 6} h</span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Especies en riesgo</span><span class="ruled-desc">${species}</span></span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">${panelType === "cra" ? "Acción recomendada C.R.A" : "Valor analítico B2B / ESG"}</span><span class="ruled-desc">${panelType === "cra" ? (tech.accion_recomendada_cra || "Monitoreo activo") : (tech.valor_analitico_b2b_academia || tech.accion_recomendada_cra || "Trazabilidad ESG")}</span></span>
        </div>
        <div class="ruled-row">
          <span class="ruled-copy"><span class="ruled-title">Normativa aplicable</span><span class="ruled-desc">${tech.normativa_aplicable || "Resolución 1263 de 2018"}</span></span>
        </div>
      </div>
    `;
    detailDialog.showModal();
  }

  // Render pins on compact dashboard map, pure live map, and maximized dialog map
  function renderPinsInto(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const items = getFilteredReports(true);
    el.innerHTML = "";

    items.forEach((r) => {
      const pos = getCoords(r);
      const sev = normSeverity(r);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-pin";
      btn.dataset.severity = sev;
      btn.style.left = `${pos.x}%`;
      btn.style.top = `${pos.y}%`;
      btn.setAttribute("aria-label", `${r.location?.zone_title || pos.label}: ${sev}`);
      btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.58 2 4 5.58 4 10c0 5.25 8 12 8 12s8-6.75 8-12c0-4.42-3.58-8-8-8Z" fill="currentColor" stroke="#163a52" stroke-width="1.5"/><circle cx="12" cy="10" r="3" fill="#ffffff"/></svg>`;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openReportDetail(r);
      });
      el.appendChild(btn);
    });
  }

  function renderAllPins() {
    renderPinsInto("dash-map-pins");
    renderPinsInto("pure-map-pins");
    renderPinsInto("dialog-map-pins");
  }

  // Render Dashboard Option 2 (Executive Bands)
  function renderDashboard() {
    const items = getTenantReports();
    const maxRisk = items.length
      ? Math.max(...items.map((r) => Number(r?.cra_technical_report?.indice_riesgo_ambiental || 0)))
      : 0;

    document.getElementById("dash-active-count").innerHTML = `${items.length}<span class="u">activas</span>`;
    document.getElementById("dash-max-risk").innerHTML = `${maxRisk}<span class="u">/100</span>`;
    document.getElementById("nav-alert-count").textContent = String(items.length);

    const lastAiEl = document.getElementById("dash-last-ai");
    const lastAiSub = document.getElementById("dash-last-ai-sub");
    if (items.length > 0) {
      const latest = items[0];
      const conf = latest?.cra_technical_report?.puntaje_confianza_ia ?? 0;
      lastAiEl.innerHTML = `${conf}<span class="u">% IA</span>`;
      lastAiSub.textContent = `${latest.id} en ${latest.location?.zone_title || "Atlántico"}`;
    } else {
      lastAiEl.textContent = "En espera";
      lastAiSub.textContent = state.sseConnected
        ? "Conectado al canal SSE del Bot IA (0 alertas)"
        : "Ejecuta prueba.bat para enviar alertas vía API";
    }

    const bondsCount = document.getElementById("bonds-validated-count");
    if (bondsCount) {
      bondsCount.innerHTML = `${items.length}<span class="u">reportes</span>`;
    }
  }

  // Render Gestión de Alertas Option 3 (4 Escalation Cards + Read-Only AI Monitoring Table)
  const escCards = document.querySelectorAll(".esc-card[data-sev]");
  escCards.forEach((card) => {
    card.addEventListener("click", () => {
      const sev = card.dataset.sev;
      state.severityFilter = state.severityFilter === sev ? null : sev;
      renderAlertas();
    });
  });

  function renderAlertas() {
    const base = getTenantReports();
    const counts = { "CRÍTICA": 0, ALTA: 0, MEDIA: 0, BAJA: 0 };
    base.forEach((r) => {
      const s = normSeverity(r);
      if (counts[s] !== undefined) counts[s] += 1;
    });

    document.getElementById("esc-cnt-critica").textContent = String(counts["CRÍTICA"]);
    document.getElementById("esc-cnt-alta").textContent = String(counts.ALTA);
    document.getElementById("esc-cnt-media").textContent = String(counts.MEDIA);
    document.getElementById("esc-cnt-baja").textContent = String(counts.BAJA);

    escCards.forEach((c) => {
      c.setAttribute("aria-pressed", String(state.severityFilter === c.dataset.sev));
    });

    const filtered = getFilteredReports(false);
    const tbody = document.getElementById("alerts-tbody");
    const emptyBox = document.getElementById("alerts-empty");
    const tableWrap = document.getElementById("alerts-table-wrap");
    document.getElementById("alerts-count-label").textContent = `${filtered.length} registros`;

    if (!filtered.length) {
      tableWrap.style.display = "none";
      emptyBox.style.display = "grid";
      return;
    }

    emptyBox.style.display = "none";
    tableWrap.style.display = "block";
    tbody.innerHTML = "";

    filtered.forEach((r) => {
      const sev = normSeverity(r);
      const tech = r.cra_technical_report || {};
      const tr = document.createElement("tr");
      if (sev === "CRÍTICA") tr.className = "row--critical";
      else if (sev === "ALTA") tr.className = "row--high";

      const verdictText = tech.es_valida === false ? "Descartada por IA" : "Verificada por IA";
      tr.innerHTML = `
        <td class="num">${r.id}</td>
        <td><strong>${r.location?.zone_title || r.location?.zone_id || "Atlántico"}</strong></td>
        <td>${tech.titulo_hallazgo || r.incident?.citizen_description || "Reporte recibido"}</td>
        <td><span class="badge badge--${sev}">${sev}</span></td>
        <td class="num">${tech.indice_riesgo_ambiental ?? 0}<span class="u">/100</span></td>
        <td>${verdictText} (${tech.puntaje_confianza_ia ?? 0}%)</td>
        <td><span class="badge badge--info">${r.status || "RECIBIDA"}</span></td>
        <td><button type="button" class="btn-line" data-open-id="${r.id}">Ver informe IA</button></td>
      `;
      tr.querySelector("button").addEventListener("click", () => openReportDetail(r));
      tbody.appendChild(tr);
    });
  }

  // Render Subscribers (CRA view connected to GET /api/subscribers)
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

  // Unified Export Center (CSV, GeoJSON, Print/PDF)
  function downloadFile(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  document.getElementById("exp-csv").addEventListener("click", () => {
    const items = getTenantReports();
    const header = ["ID", "Sector", "Hallazgo", "Severidad", "Indice_Riesgo", "Confianza_IA%", "Estado"];
    const rows = items.map((r) => [
      r.id,
      `"${(r.location?.zone_title || "").replace(/"/g, "'")}"`,
      `"${(r.cra_technical_report?.titulo_hallazgo || r.incident?.citizen_description || "").replace(/"/g, "'")}"`,
      normSeverity(r),
      r.cra_technical_report?.indice_riesgo_ambiental ?? 0,
      r.cra_technical_report?.puntaje_confianza_ia ?? 0,
      r.status || "",
    ]);
    downloadFile(`mokana-${panelType}-alertas.csv`, [header.join(","), ...rows.map((r) => r.join(","))].join("\n"), "text/csv;charset=utf-8;");
  });

  document.getElementById("exp-geojson").addEventListener("click", () => {
    const items = getTenantReports();
    const fc = {
      type: "FeatureCollection",
      features: items.map((r) => ({
        type: "Feature",
        properties: {
          id: r.id,
          sector: r.location?.zone_title || "",
          severidad: normSeverity(r),
          indice_riesgo: r.cra_technical_report?.indice_riesgo_ambiental ?? 0,
          confianza_ia: r.cra_technical_report?.puntaje_confianza_ia ?? 0,
        },
        geometry: {
          type: "Point",
          coordinates: [Number(r.location?.lng || -74.8461), Number(r.location?.lat || 11.0458)],
        },
      })),
    };
    downloadFile(`mokana-${panelType}-alertas.geojson`, JSON.stringify(fc, null, 2), "application/geo+json;charset=utf-8;");
  });

  document.getElementById("exp-pdf").addEventListener("click", () => window.print());

  // Search
  document.getElementById("search-global").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    renderAll();
  });

  // Network & Bot API SSE Status
  const netChip = document.getElementById("net-status");
  const netLabel = document.getElementById("net-label");
  const botStatusEl = document.getElementById("bot-api-status");

  function updateStatusUI() {
    const offline = !navigator.onLine;
    netChip.dataset.offline = String(offline);
    if (offline) {
      netLabel.textContent = "Sin conexión";
      if (botStatusEl) botStatusEl.textContent = "Bot IA: Sin red (caché local)";
    } else if (state.sseConnected) {
      netLabel.textContent = "Bot IA en vivo";
      if (botStatusEl) botStatusEl.textContent = "Bot IA: Conectado (SSE en vivo)";
    } else {
      netLabel.textContent = "En línea";
      if (botStatusEl) botStatusEl.textContent = "Bot IA: Sincronizado vía API";
    }
  }

  window.addEventListener("online", updateStatusUI);
  window.addEventListener("offline", updateStatusUI);

  function renderAll() {
    renderDashboard();
    renderAllPins();
    renderAlertas();
    renderSubscribers();
    updateStatusUI();
  }

  // Live API Fetch + Real-Time SSE Stream (https://mokana.joshual.tech proxied via /api/*)
  async function loadFromBotApi() {
    try {
      const res = await fetch("/api/reports", { headers: { Accept: "application/json" } });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.reports)) {
          allReports = data.reports;
        }
      }
    } catch {
      // Keep clean 0-alert state if offline or API unreachable
    }

    if (panelType === "cra") {
      try {
        const sRes = await fetch("/api/subscribers", { headers: { Accept: "application/json" } });
        if (sRes.ok) {
          const sData = await sRes.json();
          subscribers = Array.isArray(sData) ? sData : (sData.subscribers || []);
        }
      } catch {
        // Ignore when offline
      }
    }
    renderAll();
  }

  function connectSSE() {
    if (typeof EventSource === "undefined") return;
    try {
      const es = new EventSource("/api/events/stream");
      es.onopen = () => {
        state.sseConnected = true;
        updateStatusUI();
      };
      es.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.event === "report.created" && payload.data) {
            const exists = allReports.some((r) => r.id === payload.data.id);
            if (!exists) allReports.unshift(payload.data);
            renderAll();
          } else if (payload.event === "report.updated" && payload.data) {
            const idx = allReports.findIndex((r) => r.id === payload.data.id);
            if (idx !== -1) allReports[idx] = payload.data;
            else allReports.unshift(payload.data);
            renderAll();
          } else if (payload.event === "subscriber.created" && payload.data) {
            subscribers.unshift(payload.data);
            renderSubscribers();
          }
        } catch {
          // Ignore keepalive heartbeats
        }
      };
      es.onerror = () => {
        state.sseConnected = false;
        updateStatusUI();
      };
    } catch {
      state.sseConnected = false;
    }
  }

  // Manual refresh button for instant verification after prueba.bat
  const refreshBtn = document.getElementById("btn-refresh-api");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadFromBotApi());
  }

  renderAll();
  loadFromBotApi();
  connectSSE();
})();
