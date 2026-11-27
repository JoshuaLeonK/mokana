<?php
declare(strict_types=1);

session_set_cookie_params([
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_start();

require_once dirname(__DIR__) . '/src/Services/BotApiProxy.php';

use Mokana\Services\BotApiProxy;

const DEMO_USERS = [
    'admin@cra.gov.co' => [
        'password' => 'CraMokana2026!',
        'role'     => 'cra',
        'name'     => 'Coordinación C.R.A',
        'redirect' => '/cra',
    ],
    'operaciones@puertoverde.com' => [
        'password' => 'EmpresaMokana2026!',
        'role'     => 'empresa',
        'name'     => 'Puerto Verde Logística',
        'redirect' => '/empresa',
    ],
];

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(16));
}

$uriPath = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$query   = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_QUERY) ?: '';
$method  = $_SERVER['REQUEST_METHOD'] ?? 'GET';

// 1. Proxy transparente hacia la API real del Bot Mokaná (https://mokana.joshual.tech)
if (str_starts_with($uriPath, '/api/')) {
    BotApiProxy::forward($uriPath, $query);
}

// 2. Logout
if ($uriPath === '/auth/logout.php' || $uriPath === '/logout') {
    $_SESSION = [];
    session_destroy();
    header('Location: /login');
    exit;
}

// 3. Login POST (bloqueo cruzado estricto C.R.A vs Empresa)
if ($uriPath === '/auth/login.php' && $method === 'POST') {
    $email       = strtolower(trim((string) ($_POST['email'] ?? '')));
    $pass        = (string) ($_POST['password'] ?? '');
    $selectedTab = ($_POST['tenant_type'] ?? 'cra') === 'subscriber' ? 'empresa' : 'cra';
    $user        = DEMO_USERS[$email] ?? null;

    if ($user !== null && hash_equals($user['password'], $pass)) {
        if ($user['role'] !== $selectedTab) {
            $csrfToken  = $_SESSION['csrf_token'];
            $flashError = 'Esta cuenta no corresponde al tipo de acceso seleccionado.';
            $oldEmail   = $email;
            $oldTenant  = $selectedTab === 'empresa' ? 'subscriber' : 'cra';
            http_response_code(401);
            require dirname(__DIR__) . '/views/auth/login.php';
            exit;
        }
        session_regenerate_id(true);
        $_SESSION['user_email'] = $email;
        $_SESSION['user_name']  = $user['name'];
        $_SESSION['role']       = $user['role'];
        header('Location: ' . $user['redirect']);
        exit;
    }

    $csrfToken  = $_SESSION['csrf_token'];
    $flashError = 'Credenciales inválidas. Verifica tu correo y contraseña.';
    $oldEmail   = $email;
    $oldTenant  = $selectedTab === 'empresa' ? 'subscriber' : 'cra';
    http_response_code(401);
    require dirname(__DIR__) . '/views/auth/login.php';
    exit;
}

// 4. Pantalla C.R.A
if ($uriPath === '/cra') {
    if (($_SESSION['role'] ?? '') !== 'cra') {
        header('Location: /login');
        exit;
    }
    require dirname(__DIR__) . '/views/cra/index.php';
    exit;
}

// 5. Pantalla Empresa
if ($uriPath === '/empresa') {
    if (($_SESSION['role'] ?? '') !== 'empresa') {
        header('Location: /login');
        exit;
    }
    require dirname(__DIR__) . '/views/empresa/index.php';
    exit;
}

// 6. Login (GET / o /login)
$csrfToken  = $_SESSION['csrf_token'];
$flashError = null;
$oldEmail   = '';
$oldTenant  = 'cra';
require dirname(__DIR__) . '/views/auth/login.php';
