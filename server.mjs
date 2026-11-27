import http from "node:http";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, "public");
const VIEWS_DIR = path.join(__dirname, "views");
const BOT_API_HOST = "mokana.joshual.tech";
const PORT = 4175;

const USERS = {
  "admin@cra.gov.co": {
    password: "CraMokana2026!",
    role: "cra",
    redirect: "/cra",
  },
  "operaciones@puertoverde.com": {
    password: "EmpresaMokana2026!",
    role: "empresa",
    redirect: "/empresa",
  },
};

const sessions = new Map();

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".json": "application/json; charset=utf-8",
};

function parseCookies(req) {
  const out = {};
  const raw = req.headers.cookie || "";
  raw.split(";").forEach((pair) => {
    const idx = pair.indexOf("=");
    if (idx > -1) out[pair.slice(0, idx).trim()] = decodeURIComponent(pair.slice(idx + 1).trim());
  });
  return out;
}

function getSession(req) {
  const sid = parseCookies(req).mokana_sid;
  return sid ? sessions.get(sid) || null : null;
}

function renderLoginHtml({ flashError = "", oldEmail = "", oldTenant = "cra" } = {}) {
  const isSub = oldTenant === "subscriber";
  const phpRaw = fs.readFileSync(path.join(VIEWS_DIR, "auth", "login.php"), "utf8");
  const htmlStart = phpRaw.indexOf("<!DOCTYPE html>");
  let html = phpRaw.slice(htmlStart);

  // Replace PHP template expressions cleanly for local Node preview
  html = html
    .replaceAll("<?= htmlspecialchars($oldTenant, ENT_QUOTES, 'UTF-8') ?>", isSub ? "subscriber" : "cra")
    .replaceAll("<?= $oldTenant === 'cra' ? 'true' : 'false' ?>", isSub ? "false" : "true")
    .replaceAll("<?= $oldTenant === 'subscriber' ? 'true' : 'false' ?>", isSub ? "true" : "false")
    .replaceAll("<?= htmlspecialchars($csrfToken, ENT_QUOTES, 'UTF-8') ?>", "preview-csrf-token")
    .replaceAll("<?= $flashError ? 'true' : 'false' ?>", flashError ? "true" : "false")
    .replaceAll("<?= $flashError ? 'error' : 'info' ?>", flashError ? "error" : "info")
    .replaceAll("<?= $flashError ? htmlspecialchars($flashError, ENT_QUOTES, 'UTF-8') : '' ?>", flashError)
    .replaceAll("<?= htmlspecialchars($emailLabel, ENT_QUOTES, 'UTF-8') ?>", isSub ? "Correo corporativo" : "Correo institucional")
    .replaceAll("<?= htmlspecialchars($oldEmail, ENT_QUOTES, 'UTF-8') ?>", oldEmail)
    .replaceAll("<?= htmlspecialchars($emailPh, ENT_QUOTES, 'UTF-8') ?>", isSub ? "equipo@empresa.com" : "nombre@cra.gov.co");

  return html;
}

function renderPhpView(relPath) {
  const raw = fs.readFileSync(path.join(VIEWS_DIR, relPath), "utf8");
  const idx = raw.indexOf("<!DOCTYPE html>");
  return idx >= 0 ? raw.slice(idx) : raw;
}

function proxyToBotApi(req, res) {
  const isStream = req.url.startsWith("/api/events/stream");
  const options = {
    hostname: BOT_API_HOST,
    port: 443,
    path: req.url,
    method: req.method,
    headers: {
      Accept: isStream ? "text/event-stream" : "application/json",
      "User-Agent": "Mokana-Web-Panel/1.0",
    },
  };
  if (req.headers["content-type"]) {
    options.headers["Content-Type"] = req.headers["content-type"];
  }

  const proxyReq = https.request(options, (proxyRes) => {
    const outHeaders = {
      "Content-Type": proxyRes.headers["content-type"] || (isStream ? "text/event-stream" : "application/json"),
    };
    if (isStream) {
      outHeaders["Cache-Control"] = "no-cache";
      outHeaders["Connection"] = "keep-alive";
    }
    res.writeHead(proxyRes.statusCode || 200, outHeaders);
    proxyRes.pipe(res);
  });

  proxyReq.on("error", (err) => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ error: "Bot API unreachable", detail: err.message }));
  });

  req.pipe(proxyReq);
}

const server = http.createServer((req, res) => {
  const urlObj = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = urlObj.pathname;

  // 1. Live Bot API Proxy (REST + SSE)
  if (pathname.startsWith("/api/")) {
    return proxyToBotApi(req, res);
  }

  // 2. Static Assets from public/assets/*
  if (pathname.startsWith("/assets/")) {
    const filePath = path.join(PUBLIC_DIR, pathname);
    if (!filePath.startsWith(PUBLIC_DIR) || !fs.existsSync(filePath)) {
      res.writeHead(404);
      return res.end("Not found");
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
    return fs.createReadStream(filePath).pipe(res);
  }

  // 3. Logout
  if (pathname === "/auth/logout.php" || pathname === "/logout") {
    const sid = parseCookies(req).mokana_sid;
    if (sid) sessions.delete(sid);
    res.writeHead(302, {
      "Set-Cookie": "mokana_sid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
      Location: "/login",
    });
    return res.end();
  }

  // 4. Login POST
  if (pathname === "/auth/login.php" && req.method === "POST") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      const params = new URLSearchParams(body);
      const email = (params.get("email") || "").trim().toLowerCase();
      const password = params.get("password") || "";
      const tenantType = params.get("tenant_type") || "cra";
      const user = USERS[email];

      if (user && user.password === password) {
        const sid = crypto.randomBytes(16).toString("hex");
        sessions.set(sid, { email, role: user.role });
        res.writeHead(302, {
          "Set-Cookie": `mokana_sid=${sid}; Path=/; HttpOnly; SameSite=Lax`,
          Location: user.redirect,
        });
        return res.end();
      }

      res.writeHead(401, { "Content-Type": "text/html; charset=utf-8" });
      return res.end(
        renderLoginHtml({
          flashError: "Credenciales inválidas. Verifica tu correo y contraseña.",
          oldEmail: email,
          oldTenant: tenantType,
        })
      );
    });
    return;
  }

  // 5. Pantalla C.R.A
  if (pathname === "/cra") {
    const sess = getSession(req);
    if (!sess || sess.role !== "cra") {
      res.writeHead(302, { Location: "/login" });
      return res.end();
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(renderPhpView(path.join("cra", "index.php")));
  }

  // 6. Pantalla Empresa
  if (pathname === "/empresa") {
    const sess = getSession(req);
    if (!sess || sess.role !== "empresa") {
      res.writeHead(302, { Location: "/login" });
      return res.end();
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(renderPhpView(path.join("empresa", "index.php")));
  }

  // 7. Login GET
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(renderLoginHtml());
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Mokana Web (Login + CRA + Empresa + Bot API Proxy) listo en http://localhost:${PORT}`);
});
