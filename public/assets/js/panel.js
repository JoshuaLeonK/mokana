(() => {
  "use strict";

  document.documentElement.classList.add("js-ready");

  const panelType = document.body.dataset.panel || "cra"; // "cra" | "empresa"

  // Coordenadas porcentuales sobre relieve.jpg (Atlántico C.R.A)
  const ZONE_COORDS = {
    zone_mallorquin: { x: 78, y: 21, label: "Ciénaga de Mallorquín" },
    zone_balboa: { x: 64, y: 38, label: "Puerto Colombia" },
    zone_tubara: { x: 56, y: 45, label: "Tubará" },
    zone_juan_acosta: { x: 46, y: 58, label: "Juan de Acosta" },
    zone_totumo: { x: 32, y: 74, label: "Ciénaga del Totumo" },
  };

  let allReports = [];
  let subscribers = [];

  const state = {
    view: "dashboard",
    search: "",
    severityFilter: null,
  };

  // Navegación (5 vistas — sin Mapa en vivo aparte)
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

  // Helpers de formato limpio para Radicado, Zona, Anomalía, Prioridad e Informe
  function normSeverity(report) {
    const raw = (report?.cra_technical_report?.nivel_severidad || "MEDIA").toUpperCase();
    if (raw.includes("CRIT") || raw.includes("CRÍT")) return "CRÍTICA";
    if (raw.includes("ALT")) return "ALTA";
    if (raw.includes("BAJ")) return "BAJA";
    return "MEDIA";
  }

  function cleanText(str) {
    return String(str || "")
      .replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\s]+/gu, "")
      .trim();
  }

  function formatReport(r) {
    const tech = r.cra_technical_report || {};
    const radicado = r.id || "Sin radicado";
    const zona = r.location?.zone_title || ZONE_COORDS[r.location?.zone_id]?.label || "Atlántico";
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

    return { radicado, zona, anomalia, sev, riesgo, prioridad, informe, imageUrl: r.incident?.image_url || "" };
  }

  function getCoords(r) {
    const zId = r?.location?.zone_id || "zone_mallorquin";
    if (ZONE_COORDS[zId]) return ZONE_COORDS[zId];
    return { x: 64, y: 40, label: r?.location?.zone_title || "Atlántico" };
  }

  // Aislamiento Empresa: SOLO Ciénaga de Mallorquín y Puerto Colombia
  function isPaidEmpresaSector(r) {
    const zId = String(r?.location?.zone_id || "").toLowerCase();
    const zTitle = String(r?.location?.zone_title || "").toLowerCase();
    return (
      zId === "zone_mallorquin" ||
      zId === "zone_balboa" ||
      zTitle.includes("mallorqu") ||
      zTitle.includes("puerto colombia") ||
      zTitle.includes("balboa") ||
      zTitle.includes("salgar")
    );
  }

  function getTenantReports() {
    if (panelType === "empresa") {
      return allReports.filter(isPaidEmpresaSector);
    }
    return allReports;
  }

  function getFilteredReports(ignoreSeverity = false) {
    return getTenantReports().filter((r) => {
      const f = formatReport(r);
      if (!ignoreSeverity && state.severityFilter && f.sev !== state.severityFilter) return false;
      if (state.search) {
        const hay = `${f.radicado} ${f.zona} ${f.anomalia} ${f.prioridad} ${f.informe}`.toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    });
  }

  // Pan & Zoom en Modal Completo del Mapa
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

    const zIn = document.getElementById(zoomInId);
    const zOut = document.getElementById(zoomOutId);
    const zReset = document.getElementById(resetId);

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

  const dialogPan = attachPanZoom("dialog-map-viewport", "dialog-map-stage", "dialog-zoom-in", "dialog-zoom-out", "dialog-zoom-reset");

  // Abrir Modal Completo al hacer clic en el mapa del Dashboard o en "Ampliar mapa"
  const mapDialog = document.getElementById("map-dialog");
  const dashMapViewport = document.getElementById("dash-map-viewport");
  const openMapBtn = document.getElementById("btn-open-map-modal");

  function openMapModal() {
    dialogPan.reset();
    renderAllPins();
    renderMapModalSidebar();
    mapDialog.showModal();
  }

  dashMapViewport.addEventListener("click", openMapModal);
  dashMapViewport.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openMapModal();
    }
  });
  openMapBtn.addEventListener("click", openMapModal);
  document.getElementById("btn-minimize-map").addEventListener("click", () => mapDialog.close());
  mapDialog.addEventListener("click", (e) => {
    if (e.target === mapDialog) mapDialog.close();
  });

  // Modal de Detalle limpio: Radicado, Zona, Anomalía, Prioridad, Informe
  const detailDialog = document.getElementById("detail-dialog");
  document.getElementById("btn-close-detail").addEventListener("click", () => detailDialog.close());
  detailDialog.addEventListener("click", (e) => {
    if (e.target === detailDialog) detailDialog.close();
  });

  function openReportDetail(r) {
    const f = formatReport(r);
    document.getElementById("detail-title").textContent = `Radicado: ${f.radicado}`;
    const body = document.getElementById("detail-body");
    const photoHtml = f.imageUrl
      ? `<img class="detail-photo" src="${f.imageUrl}" alt="Evidencia de ${f.radicado}" />`
      : "";

    body.innerHTML = `
      ${photoHtml}
      <div class="ruled-list">
        <div class="ruled-row">
          <span class="ruled-title">Radicado</span>
          <span class="num">${f.radicado}</span>
        </div>
        <div class="ruled-row">
          <span class="ruled-title">Zona</span>
          <span>${f.zona}</span>
        </div>
        <div class="ruled-row">
          <span class="ruled-title">Anomalía</span>
          <span>${f.anomalia}</span>
        </div>
        <div class="ruled-row">
          <span class="ruled-title">Prioridad</span>
          <span class="badge badge--${f.sev}">${f.prioridad}</span>
        </div>
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

  // Pines en el mapa del Dashboard y del Modal Completo (coloreados por prioridad de riesgo)
  function renderPinsInto(containerId, openDetailOnClick) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const items = getFilteredReports(true);
    el.innerHTML = "";

    items.forEach((r) => {
      const f = formatReport(r);
      const pos = getCoords(r);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-pin";
      btn.dataset.severity = f.sev;
      btn.style.left = `${pos.x}%`;
      btn.style.top = `${pos.y}%`;
      btn.setAttribute("aria-label", `${f.zona}: ${f.prioridad}`);
      btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.58 2 4 5.58 4 10c0 5.25 8 12 8 12s8-6.75 8-12c0-4.42-3.58-8-8-8Z" fill="currentColor" stroke="#163a52" stroke-width="1.5"/><circle cx="12" cy="10" r="3" fill="#ffffff"/></svg>`;
      if (openDetailOnClick) {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          openReportDetail(r);
        });
      }
      el.appendChild(btn);
    });
  }

  function renderAllPins() {
    renderPinsInto("dash-map-pins", false);
    renderPinsInto("dialog-map-pins", true);
  }

  function renderMapModalSidebar() {
    const list = document.getElementById("map-modal-alerts-list");
    if (!list) return;
    const items = getTenantReports();
    list.innerHTML = "";

    if (!items.length) {
      list.innerHTML = `<span class="ruled-desc">Sin alertas activas en el mapa.</span>`;
      return;
    }

    items.forEach((r) => {
      const f = formatReport(r);
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
      btn.addEventListener("click", () => openReportDetail(r));
      list.appendChild(btn);
    });
  }

  // Filas limpias reutilizables para Últimas 10 alertas (Dashboard) y Gestión de Alertas
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

    items.forEach((r) => {
      const f = formatReport(r);
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
      tr.querySelector("button").addEventListener("click", () => openReportDetail(r));
      tbody.appendChild(tr);
    });
  }

  // Dashboard: Estado compacto + Últimas 10 alertas
  function renderDashboard() {
    const items = getTenantReports();
    const maxRisk = items.length
      ? Math.max(...items.map((r) => Number(r?.cra_technical_report?.indice_riesgo_ambiental || 0)))
      : 0;

    document.getElementById("dash-active-count").innerHTML = `${items.length}<span class="u">activas</span>`;
    document.getElementById("dash-max-risk").innerHTML = `${maxRisk}<span class="u">/100</span>`;
    document.getElementById("nav-alert-count").textContent = String(items.length);

    const bondsCount = document.getElementById("bonds-validated-count");
    if (bondsCount) {
      bondsCount.innerHTML = `${items.length}<span class="u">reportes</span>`;
    }

    const latestTen = getFilteredReports(true).slice(0, 10);
    renderRowsInto(latestTen, "dash-alerts-tbody", "dash-alerts-empty", "dash-alerts-table-wrap");
  }

  // Gestión de Alertas: 4 tarjetas de escalamiento + tabla limpia
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
    document.getElementById("alerts-count-label").textContent = `${filtered.length} registros`;
    renderRowsInto(filtered, "alerts-tbody", "alerts-empty", "alerts-table-wrap");
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

  // Exportar (CSV, GeoJSON, PDF)
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
    const items = getTenantReports().map(formatReport);
    const header = ["Radicado", "Zona", "Anomalia", "Prioridad", "Informe"];
    const rows = items.map((f) => [
      f.radicado,
      `"${f.zona.replace(/"/g, "'")}"`,
      `"${f.anomalia.replace(/"/g, "'")}"`,
      `"${f.prioridad}"`,
      `"${f.informe.replace(/"/g, "'")}"`,
    ]);
    downloadFile(`mokana-${panelType}-alertas.csv`, [header.join(","), ...rows.map((r) => r.join(","))].join("\n"), "text/csv;charset=utf-8;");
  });

  document.getElementById("exp-geojson").addEventListener("click", () => {
    const items = getTenantReports();
    const fc = {
      type: "FeatureCollection",
      features: items.map((r) => {
        const f = formatReport(r);
        return {
          type: "Feature",
          properties: {
            radicado: f.radicado,
            zona: f.zona,
            anomalia: f.anomalia,
            prioridad: f.prioridad,
            informe: f.informe,
          },
          geometry: {
            type: "Point",
            coordinates: [Number(r.location?.lng || -74.8461), Number(r.location?.lat || 11.0458)],
          },
        };
      }),
    };
    downloadFile(`mokana-${panelType}-alertas.geojson`, JSON.stringify(fc, null, 2), "application/geo+json;charset=utf-8;");
  });

  document.getElementById("exp-pdf").addEventListener("click", () => window.print());

  document.getElementById("search-global").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
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
    renderAllPins();
    renderMapModalSidebar();
    renderAlertas();
    renderSubscribers();
    updateNetwork();
  }

  // Carga en vivo desde API + canal SSE
  async function loadFromBotApi() {
    try {
      const res = await fetch("/api/reports", { headers: { Accept: "application/json" } });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.reports)) allReports = data.reports;
      }
    } catch {
      // Mantiene estado limpio si no hay red
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

  renderAll();
  loadFromBotApi();
  connectSSE();
})();
