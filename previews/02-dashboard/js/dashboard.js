(() => {
  "use strict";

  document.documentElement.classList.add("js-ready");

  const OFFLINE_STORAGE_KEY = "mokana_offline_reports_v1";

  const alerts = [
    {
      id: "AL-101",
      zone: "Ciénaga de Mallorquín",
      category: "agua",
      threat: "Vertimiento y turbidez hídrica severa",
      risk: 4,
      impact: 4,
      carbonRisk: 180,
      trust: 94,
      subscriberVisible: true,
      x: 78,
      y: 22,
    },
    {
      id: "AL-102",
      zone: "Puerto Velero",
      category: "presion",
      threat: "Relleno de borde y presión urbana",
      risk: 3,
      impact: 4,
      carbonRisk: 140,
      trust: 89,
      subscriberVisible: true,
      x: 64,
      y: 38,
    },
    {
      id: "AL-103",
      zone: "Bocas de Ceniza",
      category: "incendio",
      threat: "Anomalía térmica satelital activa",
      risk: 3,
      impact: 3,
      carbonRisk: 100,
      trust: 86,
      subscriberVisible: false,
      x: 82,
      y: 16,
    },
    {
      id: "AL-104",
      zone: "Ciénaga del Totumo",
      category: "agua",
      threat: "Variación de salinidad superficial",
      risk: 2,
      impact: 2,
      carbonRisk: 35,
      trust: 91,
      subscriberVisible: false,
      x: 34,
      y: 72,
    },
  ];

  let validationQueue = [
    {
      id: "RP-204",
      zone: "Ciénaga de Mallorquín",
      category: "agua",
      threat: "Descarga de residuos sólidos en canal norte",
      risk: 4,
      impact: 3,
      trust: 92,
      layers: "GPS + foto + cruce satelital C.R.A positivo",
      x: 75,
      y: 24,
    },
    {
      id: "RP-205",
      zone: "Salgar",
      category: "presion",
      threat: "Tala localizada de mangle rojo",
      risk: 3,
      impact: 4,
      trust: 78,
      layers: "GPS + evidencia fotográfica verificada",
      x: 70,
      y: 31,
    },
    {
      id: "RP-206",
      zone: "Puerto Colombia",
      category: "incendio",
      threat: "Reporte atípico sin respaldo satelital",
      risk: 4,
      impact: 4,
      trust: 42,
      layers: "Sin coincidencia satelital, revisar posible sabotaje",
      x: 68,
      y: 34,
    },
  ];

  const auditLog = [
    { id: "RP-198", text: "Descartado por sabotaje: coordenadas fuera de manglar", status: "Bloqueado" },
    { id: "RP-199", text: "Validado en Ciénaga de Mallorquín (94 % confianza)", status: "Aprobado" },
  ];

  const tenants = [
    { id: "TN-01", name: "C.R.A Atlántico", type: "Sin cobro", plan: "Acceso total", zones: "Todos los sectores", active: true, locked: true },
    { id: "TN-02", name: "Puerto Verde Logística", type: "Suscriptor", plan: "Pro", zones: "Mallorquín, Puerto Velero", active: true, locked: false },
    { id: "TN-03", name: "Energía Caribe S.A.", type: "Suscriptor", plan: "Enterprise", zones: "Mallorquín, Bocas, Totumo", active: true, locked: false },
    { id: "TN-04", name: "EcoTurismo Costero", type: "Suscriptor", plan: "Esencial", zones: "Puerto Velero", active: false, locked: false },
  ];

  const state = {
    view: "resumen",
    role: "cra",
    search: "",
    planVisible: true,
    enabledCats: new Set(["agua", "incendio", "presion"]),
    matrixCell: null, // { risk, impact }
    pickedPoint: null, // { x, y }
    lastUndo: null,
    undoTimer: null,
  };

  function getSeverity(risk, impact) {
    const score = risk * impact;
    if (score >= 12) return { key: "critical", label: "Crítico" };
    if (score >= 8) return { key: "high", label: "Alto" };
    if (score >= 4) return { key: "moderate", label: "Moderado" };
    return { key: "low", label: "Bajo" };
  }

  function levelName(n) {
    return ["", "Bajo", "Moderado", "Alto", "Crítico"][n] || "Bajo";
  }

  // Navigation — all 7 sidebar views
  const navButtons = document.querySelectorAll(".nav-item[data-view]");
  const viewPanels = document.querySelectorAll(".view-panel");
  const sidebar = document.getElementById("sidebar");
  const menuToggle = document.getElementById("menu-toggle");

  function switchView(viewName) {
    if (state.role === "subscriber" && (viewName === "validacion" || viewName === "tenants")) {
      viewName = "resumen";
    }
    if (state.role === "cra" && viewName === "suscripcion") {
      viewName = "tenants";
    }
    state.view = viewName;

    navButtons.forEach((btn) => {
      if (btn.dataset.view === viewName) {
        btn.setAttribute("aria-current", "page");
      } else {
        btn.removeAttribute("aria-current");
      }
    });

    viewPanels.forEach((panel) => {
      panel.dataset.active = String(panel.id === `view-${viewName}`);
    });

    sidebar.dataset.open = "false";
    menuToggle.setAttribute("aria-expanded", "false");
  }

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });

  document.querySelectorAll("[data-jump-view]").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.jumpView));
  });

  document.getElementById("btn-go-export").addEventListener("click", () => switchView("exportar"));

  menuToggle.addEventListener("click", () => {
    const open = sidebar.dataset.open === "true";
    sidebar.dataset.open = String(!open);
    menuToggle.setAttribute("aria-expanded", String(!open));
  });

  // Pan & Zoom Controller for compact + maximized maps
  function createPanZoom(viewportId, stageId, zoomInId, zoomOutId, resetId) {
    const viewport = document.getElementById(viewportId);
    const stage = document.getElementById(stageId);
    const zIn = document.getElementById(zoomInId);
    const zOut = document.getElementById(zoomOutId);
    const zReset = document.getElementById(resetId);

    let scale = 1;
    let tx = 0;
    let ty = 0;
    let dragging = false;
    let sx = 0;
    let sy = 0;

    function apply() {
      const mx = (viewport.clientWidth * (scale - 1)) / 2;
      const my = (viewport.clientHeight * (scale - 1)) / 2;
      tx = Math.max(-mx, Math.min(mx, tx));
      ty = Math.max(-my, Math.min(my, ty));
      stage.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      zReset.textContent = `${Math.round(scale * 100)}%`;
    }

    function setZoom(next) {
      scale = Math.max(1, Math.min(3, Number(next.toFixed(2))));
      if (scale === 1) {
        tx = 0;
        ty = 0;
      }
      apply();
    }

    zIn.addEventListener("click", () => setZoom(scale + 0.35));
    zOut.addEventListener("click", () => setZoom(scale - 0.35));
    zReset.addEventListener("click", () => setZoom(1));

    viewport.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".map-pin") || e.target.closest(".map-popover") || scale <= 1) return;
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

  createPanZoom("map-viewport", "map-stage", "zoom-in", "zoom-out", "zoom-reset");
  const dialogPan = createPanZoom("dialog-map-viewport", "dialog-map-stage", "dialog-zoom-in", "dialog-zoom-out", "dialog-zoom-reset");

  // Maximize / Minimize Dialog
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

  // Vantage Layer Switches
  document.getElementById("sw-plan").addEventListener("change", (e) => {
    state.planVisible = e.target.checked;
    ["map-plan-img", "live-map-plan-img", "dialog-map-plan-img"].forEach((id) => {
      document.getElementById(id).dataset.hidden = String(!state.planVisible);
    });
  });

  document.querySelectorAll(".layer-cat").forEach((sw) => {
    sw.addEventListener("change", () => {
      if (sw.checked) state.enabledCats.add(sw.dataset.cat);
      else state.enabledCats.delete(sw.dataset.cat);
      renderAll();
    });
  });

  // Filtered alerts
  function getVisibleAlerts(ignoreMatrix = false) {
    return alerts.filter((a) => {
      if (state.role === "subscriber" && !a.subscriberVisible) return false;
      if (!state.enabledCats.has(a.category)) return false;
      if (!ignoreMatrix && state.matrixCell) {
        if (a.risk !== state.matrixCell.risk || a.impact !== state.matrixCell.impact) return false;
      }
      if (state.search) {
        const hay = `${a.zone} ${a.threat} ${a.id}`.toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    });
  }

  // Render Map Pins across all 3 map views
  const mapPopover = document.getElementById("map-popover");
  const popoverZone = document.getElementById("popover-zone");
  const popoverThreat = document.getElementById("popover-threat");
  const popoverScore = document.getElementById("popover-score");
  document.getElementById("popover-close").addEventListener("click", () => {
    mapPopover.dataset.open = "false";
  });

  function renderPinsInto(containerId, includePicked) {
    const el = document.getElementById(containerId);
    const items = getVisibleAlerts(true);
    el.innerHTML = "";

    items.forEach((a) => {
      const sev = getSeverity(a.risk, a.impact);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-pin";
      btn.dataset.severity = sev.key;
      btn.style.left = `${a.x}%`;
      btn.style.top = `${a.y}%`;
      btn.setAttribute("aria-label", `${a.zone}: ${a.threat}`);
      btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.58 2 4 5.58 4 10c0 5.25 8 12 8 12s8-6.75 8-12c0-4.42-3.58-8-8-8Z" fill="currentColor" stroke="#163a52" stroke-width="1.5"/><circle cx="12" cy="10" r="3" fill="#ffffff"/></svg>`;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        popoverZone.textContent = a.zone;
        popoverThreat.textContent = a.threat;
        popoverScore.textContent = `Índice ${a.risk * a.impact}/16, confianza ${a.trust}%`;
        mapPopover.dataset.open = "true";
      });
      el.appendChild(btn);
    });

    if (includePicked && state.pickedPoint) {
      const marker = document.createElement("span");
      marker.className = "map-pin";
      marker.dataset.severity = "critical";
      marker.style.left = `${state.pickedPoint.x}%`;
      marker.style.top = `${state.pickedPoint.y}%`;
      marker.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="currentColor" stroke="#ffffff" stroke-width="2"/></svg>`;
      el.appendChild(marker);
    }
  }

  function renderAllPins() {
    renderPinsInto("map-pins", false);
    renderPinsInto("dialog-map-pins", false);
    renderPinsInto("live-map-pins", true);
  }

  // Click on Live Map to pick coordinates for new report
  const liveMapViewport = document.getElementById("live-map-viewport");
  const pickedCoords = document.getElementById("picked-coords");
  liveMapViewport.addEventListener("click", (e) => {
    const rect = liveMapViewport.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 100);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 100);
    state.pickedPoint = { x, y };
    pickedCoords.textContent = `Coordenada fijada: ${x}%, ${y}%`;
    renderPinsInto("live-map-pins", true);
  });

  // Offline Queue Storage helpers
  function getOfflineQueue() {
    try {
      return JSON.parse(localStorage.getItem(OFFLINE_STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveOfflineQueue(list) {
    try {
      localStorage.setItem(OFFLINE_STORAGE_KEY, JSON.stringify(list));
    } catch {
      // Ignore storage quota errors in preview
    }
  }

  // New Georeferenced Report Form (works online & offline)
  const reportForm = document.getElementById("report-form");
  const reportFeedback = document.getElementById("report-feedback");
  reportForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const desc = document.getElementById("rep-desc").value.trim();
    if (!desc) {
      reportFeedback.textContent = "Describe la situación observada antes de enviar.";
      return;
    }

    const newRep = {
      id: `RP-${Math.floor(300 + Math.random() * 600)}`,
      zone: document.getElementById("rep-zone").value,
      category: document.getElementById("rep-cat").value,
      threat: desc,
      risk: Number(document.getElementById("rep-risk").value),
      impact: Number(document.getElementById("rep-impact").value),
      trust: state.pickedPoint ? 84 : 68,
      layers: state.pickedPoint ? "Coordenada GPS fijada en mapa" : "Ubicación por sector",
      x: state.pickedPoint ? state.pickedPoint.x : 70,
      y: state.pickedPoint ? state.pickedPoint.y : 35,
    };

    if (!navigator.onLine) {
      const q = getOfflineQueue();
      q.push(newRep);
      saveOfflineQueue(q);
      reportFeedback.textContent = `Sin conexión: ${newRep.id} guardado en cola local (${q.length} pendientes).`;
    } else {
      validationQueue.unshift(newRep);
      reportFeedback.textContent = `${newRep.id} enviado a la cola de validación anti-sabotaje.`;
    }

    reportForm.reset();
    state.pickedPoint = null;
    pickedCoords.textContent = "Sin punto fijado";
    updateNetwork();
    renderAll();
  });

  // 4x4 Thermal Matrix (Psychological Impact)
  const matrixGrid = document.getElementById("matrix-grid");
  const matrixActiveLabel = document.getElementById("matrix-active-label");
  document.getElementById("btn-clear-matrix").addEventListener("click", () => {
    state.matrixCell = null;
    matrixActiveLabel.textContent = "Filtro: todas";
    renderAll();
  });

  function renderMatrix() {
    const baseItems = getVisibleAlerts(true);
    matrixGrid.innerHTML = "";

    const headerLabels = ["Riesgo / Imp.", "1 Bajo", "2 Mod.", "3 Alto", "4 Crítico"];
    headerLabels.forEach((lbl) => {
      const div = document.createElement("div");
      div.className = "matrix-axis";
      div.textContent = lbl;
      matrixGrid.appendChild(div);
    });

    for (let r = 4; r >= 1; r--) {
      const axis = document.createElement("div");
      axis.className = "matrix-axis";
      axis.textContent = `${r} ${levelName(r)}`;
      matrixGrid.appendChild(axis);

      for (let imp = 1; imp <= 4; imp++) {
        const count = baseItems.filter((a) => a.risk === r && a.impact === imp).length;
        const sev = getSeverity(r, imp);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `matrix-cell cell--${sev.key}`;
        const active = state.matrixCell && state.matrixCell.risk === r && state.matrixCell.impact === imp;
        btn.setAttribute("aria-pressed", String(Boolean(active)));
        btn.innerHTML = `<span class="cell-count">${count}</span><span class="cell-score">${r * imp}/16</span>`;
        btn.addEventListener("click", () => {
          if (active) {
            state.matrixCell = null;
            matrixActiveLabel.textContent = "Filtro: todas";
          } else {
            state.matrixCell = { risk: r, impact: imp };
            matrixActiveLabel.textContent = `Filtro: Riesgo ${r} × Impacto ${imp} (${r * imp}/16)`;
          }
          renderMatrix();
          renderAlertTables();
        });
        matrixGrid.appendChild(btn);
      }
    }
  }

  // Render High-Urgency Tables (Summary + Full)
  function renderAlertTables() {
    const summaryTbody = document.getElementById("summary-alerts-tbody");
    const fullTbody = document.getElementById("full-alerts-tbody");
    const items = getVisibleAlerts(false).sort((a, b) => b.risk * b.impact - a.risk * a.impact);

    document.getElementById("full-table-count").textContent = `${items.length} alertas`;

    const buildRows = (list, target, isSummary) => {
      target.innerHTML = "";
      if (!list.length) {
        target.innerHTML = `<tr><td colspan="7">Sin alertas para el filtro seleccionado.</td></tr>`;
        return;
      }
      list.forEach((a) => {
        const score = a.risk * a.impact;
        const sev = getSeverity(a.risk, a.impact);
        const pct = Math.round((score / 16) * 100);
        const tr = document.createElement("tr");
        tr.className = `row--${sev.key}`;
        tr.innerHTML = isSummary
          ? `
            <td><strong>${a.zone}</strong></td>
            <td>${a.threat}</td>
            <td><span class="badge badge--${sev.key}">${sev.label}</span></td>
            <td class="num">${score}<span class="u">/16</span></td>
            <td><div class="urgency-meter" aria-hidden="true"><div class="urgency-fill fill--${sev.key}" style="width:${pct}%"></div></div></td>
            <td class="num">${a.carbonRisk}<span class="u">tCO₂</span></td>
            <td class="num">${a.trust}<span class="u">%</span></td>
          `
          : `
            <td><strong>${a.zone}</strong></td>
            <td>${a.threat}</td>
            <td><span class="badge badge--${sev.key}">${levelName(a.risk)}</span></td>
            <td>${levelName(a.impact)}</td>
            <td class="num">${score}<span class="u">/16</span></td>
            <td><div class="urgency-meter" aria-hidden="true"><div class="urgency-fill fill--${sev.key}" style="width:${pct}%"></div></div></td>
            <td class="num">${a.trust}<span class="u">%</span></td>
          `;
        target.appendChild(tr);
      });
    };

    buildRows(getVisibleAlerts(true).sort((a, b) => b.risk * b.impact - a.risk * a.impact), summaryTbody, true);
    buildRows(items, fullTbody, false);
  }

  // Anti-Sabotage Validation Queue + Audit Log
  const queueList = document.getElementById("queue-list");
  const auditLogEl = document.getElementById("audit-log");
  const undoBar = document.getElementById("undo-bar");
  const undoText = document.getElementById("undo-text");
  const navPendingCount = document.getElementById("nav-pending-count");

  function renderValidation() {
    navPendingCount.textContent = String(validationQueue.length);
    queueList.innerHTML = "";

    if (!validationQueue.length) {
      queueList.innerHTML = `<p class="ruled-desc">Cola al día: todos los reportes fueron auditados.</p>`;
    } else {
      validationQueue.forEach((item) => {
        const row = document.createElement("div");
        row.className = "queue-row";
        row.innerHTML = `
          <div class="panel-head" style="margin-bottom:0">
            <span class="ruled-title">${item.zone} (${item.id})</span>
            <span class="badge badge--${getSeverity(item.risk, item.impact).key}">${item.risk * item.impact}/16</span>
          </div>
          <span class="ruled-desc">${item.threat} (${item.layers})</span>
          <div class="trust-row">
            <div class="trust-track"><div class="trust-fill" data-low="${item.trust < 60}" style="width:${item.trust}%"></div></div>
            <span class="num ruled-desc">${item.trust}%</span>
          </div>
          <div class="toolbar-row">
            <button type="button" class="btn-line btn-ok" data-act="approve">Validar y publicar</button>
            <button type="button" class="btn-line btn-danger" data-act="reject">Marcar sabotaje</button>
          </div>
        `;
        row.querySelectorAll("button").forEach((b) => {
          b.addEventListener("click", () => decideQueue(item, b.dataset.act, row));
        });
        queueList.appendChild(row);
      });
    }

    auditLogEl.innerHTML = "";
    auditLog.slice(0, 6).forEach((entry) => {
      const div = document.createElement("div");
      div.className = "ruled-row";
      div.innerHTML = `
        <span class="ruled-copy"><span class="ruled-title">${entry.id}</span><span class="ruled-desc">${entry.text}</span></span>
        <span class="badge ${entry.status === "Aprobado" ? "badge--low" : "badge--critical"}">${entry.status}</span>
      `;
      auditLogEl.appendChild(div);
    });
  }

  function decideQueue(item, act, rowEl) {
    rowEl.dataset.leaving = "true";
    window.setTimeout(() => {
      const idx = validationQueue.findIndex((q) => q.id === item.id);
      if (idx === -1) return;
      validationQueue.splice(idx, 1);

      let promotedAlert = null;
      if (act === "approve") {
        promotedAlert = {
          id: item.id,
          zone: item.zone,
          category: item.category,
          threat: item.threat,
          risk: item.risk,
          impact: item.impact,
          carbonRisk: 90,
          trust: item.trust,
          subscriberVisible: item.zone === "Ciénaga de Mallorquín" || item.zone === "Puerto Velero",
          x: item.x,
          y: item.y,
        };
        alerts.unshift(promotedAlert);
        auditLog.unshift({ id: item.id, text: `Validado en ${item.zone} (${item.trust} % confianza)`, status: "Aprobado" });
      } else {
        auditLog.unshift({ id: item.id, text: `Descartado como posible sabotaje en ${item.zone}`, status: "Bloqueado" });
      }

      state.lastUndo = { item, index: idx, act, promotedAlert };
      undoText.textContent = act === "approve" ? `${item.id} validado y publicado.` : `${item.id} bloqueado como sabotaje.`;
      undoBar.dataset.visible = "true";

      window.clearTimeout(state.undoTimer);
      state.undoTimer = window.setTimeout(() => {
        undoBar.dataset.visible = "false";
        state.lastUndo = null;
      }, 5000);

      renderAll();
    }, 160);
  }

  document.getElementById("btn-undo").addEventListener("click", () => {
    if (!state.lastUndo) return;
    const { item, index, act, promotedAlert } = state.lastUndo;
    validationQueue.splice(index, 0, item);
    if (act === "approve" && promotedAlert) {
      const aIdx = alerts.findIndex((a) => a.id === promotedAlert.id);
      if (aIdx !== -1) alerts.splice(aIdx, 1);
    }
    auditLog.shift();
    state.lastUndo = null;
    undoBar.dataset.visible = "false";
    renderAll();
  });

  // Tenants Table (C.R.A interactive management)
  function renderTenants() {
    const tbody = document.getElementById("tenants-tbody");
    tbody.innerHTML = "";
    tenants.forEach((t) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${t.name}</strong></td>
        <td>${t.type}</td>
        <td>${t.plan}</td>
        <td>${t.zones}</td>
        <td><span class="badge ${t.active ? "badge--low" : "badge--moderate"}">${t.active ? "Activo" : "Pausado"}</span></td>
        <td>${t.locked ? "<span class=\"ruled-desc\">Entidad base</span>" : `<button type="button" class="btn-line" data-tid="${t.id}">${t.active ? "Pausar" : "Activar"}</button>`}</td>
      `;
      const btn = tr.querySelector("button");
      if (btn) {
        btn.addEventListener("click", () => {
          t.active = !t.active;
          renderTenants();
        });
      }
      tbody.appendChild(tr);
    });
  }

  // KPIs & Layer counts
  function renderKpis() {
    const visible = getVisibleAlerts(true);
    const maxScore = visible.length ? Math.max(...visible.map((a) => a.risk * a.impact)) : 0;
    const totalCarbon = visible.reduce((sum, a) => sum + a.carbonRisk, 0);

    document.getElementById("cnt-agua").innerHTML = `${visible.filter((a) => a.category === "agua").length} <span class="u">alertas</span>`;
    document.getElementById("cnt-incendio").innerHTML = `${visible.filter((a) => a.category === "incendio").length} <span class="u">alertas</span>`;
    document.getElementById("cnt-presion").innerHTML = `${visible.filter((a) => a.category === "presion").length} <span class="u">alertas</span>`;
    document.getElementById("citizen-bonds-count").innerHTML = `${alerts.length}<span class="u">bonos</span>`;

    document.getElementById("kpi-1-val").innerHTML = `${visible.length}<span class="u">activas</span>`;
    document.getElementById("kpi-2-val").innerHTML = `${maxScore}<span class="u">/16</span>`;

    if (state.role === "cra") {
      document.getElementById("kpi-3-label").textContent = "Cola anti-sabotaje";
      document.getElementById("kpi-3-val").innerHTML = `${validationQueue.length}<span class="u">pendientes</span>`;
      document.getElementById("kpi-3-note").textContent = validationQueue.length ? "Revisión C.R.A requerida" : "Cola al día";
      document.getElementById("kpi-4-val").innerHTML = `${totalCarbon}<span class="u">tCO₂</span>`;
    } else {
      document.getElementById("kpi-3-label").textContent = "Cobertura de plan";
      document.getElementById("kpi-3-val").innerHTML = `Pro<span class="u">activo</span>`;
      document.getElementById("kpi-3-note").textContent = "Mallorquín y Puerto Velero";
      document.getElementById("kpi-4-val").innerHTML = `${totalCarbon}<span class="u">tCO₂</span>`;
    }
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
    const items = getVisibleAlerts(true);
    const header = ["ID", "Sector", "Amenaza", "Riesgo", "Impacto", "Indice", "Carbono_tCO2", "Confianza%"];
    const rows = items.map((a) => [a.id, `"${a.zone}"`, `"${a.threat}"`, a.risk, a.impact, `${a.risk * a.impact}/16`, a.carbonRisk, a.trust]);
    downloadFile(`mokana-informe-${state.role}.csv`, [header.join(","), ...rows.map((r) => r.join(","))].join("\n"), "text/csv;charset=utf-8;");
  });

  document.getElementById("exp-geojson").addEventListener("click", () => {
    const items = getVisibleAlerts(true);
    const fc = {
      type: "FeatureCollection",
      features: items.map((a) => ({
        type: "Feature",
        properties: {
          id: a.id,
          sector: a.zone,
          amenaza: a.threat,
          riesgo: a.risk,
          impacto: a.impact,
          indice: a.risk * a.impact,
          confianza: a.trust,
        },
        geometry: {
          type: "Point",
          coordinates: [Number((-75.2 + a.x * 0.005).toFixed(4)), Number((11.15 - a.y * 0.006).toFixed(4))],
        },
      })),
    };
    downloadFile(`mokana-alertas-${state.role}.geojson`, JSON.stringify(fc, null, 2), "application/geo+json;charset=utf-8;");
  });

  document.getElementById("exp-pdf").addEventListener("click", () => {
    window.print();
  });

  // Role Switching
  const roleSwitch = document.getElementById("role-switch");
  const roleButtons = document.querySelectorAll(".role-btn");
  function applyRole(role) {
    state.role = role;
    roleSwitch.dataset.role = role;
    roleButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.role === role)));
    document.querySelectorAll("[data-role-only]").forEach((el) => {
      el.dataset.hiddenRole = String(el.dataset.roleOnly !== role);
    });

    if (role === "cra") {
      document.getElementById("resumen-title").textContent = "Monitoreo satelital de manglares";
      document.getElementById("resumen-subtitle").textContent = "Cobertura global C.R.A del Atlántico con validación en tiempo real.";
      document.getElementById("sidebar-user").textContent = "Coordinación C.R.A";
      document.getElementById("sidebar-role").textContent = "Acceso total";
      document.getElementById("export-scope-label").textContent = "Alcance: C.R.A (todos los sectores)";
    } else {
      document.getElementById("resumen-title").textContent = "Panel empresarial de alertas";
      document.getElementById("resumen-subtitle").textContent = "Zonas contratadas con alertas verificadas y trazabilidad ESG.";
      document.getElementById("sidebar-user").textContent = "Puerto Verde Logística";
      document.getElementById("sidebar-role").textContent = "Plan Pro";
      document.getElementById("export-scope-label").textContent = "Alcance: Plan Pro (Mallorquín y Puerto Velero)";
    }

    switchView(state.view);
    renderAll();
  }

  roleButtons.forEach((b) => b.addEventListener("click", () => applyRole(b.dataset.role)));

  // Search
  document.getElementById("search-global").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    renderAll();
  });

  // Network & Offline Sync
  const netStatus = document.getElementById("net-status");
  const netLabel = document.getElementById("net-label");
  const btnSyncOffline = document.getElementById("btn-sync-offline");

  function updateNetwork() {
    const offline = !navigator.onLine;
    const queued = getOfflineQueue();
    netStatus.dataset.offline = String(offline);
    if (offline) {
      netLabel.textContent = queued.length ? `Offline (${queued.length} en cola)` : "Sin conexión";
      btnSyncOffline.style.display = "none";
    } else {
      netLabel.textContent = queued.length ? `En línea (${queued.length} por sincronizar)` : "En línea";
      btnSyncOffline.style.display = queued.length ? "inline-flex" : "none";
    }
  }

  btnSyncOffline.addEventListener("click", () => {
    const queued = getOfflineQueue();
    if (!queued.length) return;
    queued.forEach((item) => validationQueue.unshift(item));
    saveOfflineQueue([]);
    updateNetwork();
    renderAll();
  });

  window.addEventListener("online", updateNetwork);
  window.addEventListener("offline", updateNetwork);

  function renderAll() {
    renderKpis();
    renderAllPins();
    renderMatrix();
    renderAlertTables();
    renderValidation();
    renderTenants();
  }

  updateNetwork();
  applyRole("cra");
})();
