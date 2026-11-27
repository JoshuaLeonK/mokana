<?php
declare(strict_types=1);

namespace Mokana\Services;

final class BotApiProxy
{
    private const BASE_URL = 'https://mokana.joshual.tech';

    public static function forward(string $path, string $query = ''): void
    {
        $url = self::BASE_URL . $path . ($query !== '' ? '?' . $query : '');
        $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
        $isStream = str_contains($path, '/api/events/stream');

        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);

        $headers = ['Accept: ' . ($isStream ? 'text/event-stream' : 'application/json')];
        $body = file_get_contents('php://input');
        if ($body !== false && $body !== '' && in_array($method, ['POST', 'PUT', 'PATCH'], true)) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
            $headers[] = 'Content-Type: application/json';
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        if ($isStream) {
            header('Content-Type: text/event-stream');
            header('Cache-Control: no-cache');
            header('Connection: keep-alive');
            header('X-Accel-Buffering: no');
            @ob_end_flush();
            curl_setopt($ch, CURLOPT_TIMEOUT, 0);
            curl_setopt($ch, CURLOPT_WRITEFUNCTION, static function ($ch, string $chunk): int {
                echo $chunk;
                if (ob_get_level() > 0) {
                    @ob_flush();
                }
                flush();
                return strlen($chunk);
            });
            curl_exec($ch);
            curl_close($ch);
            exit;
        }

        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 20);
        $response = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        header('Content-Type: application/json; charset=utf-8');
        if ($response === false) {
            http_response_code(502);
            echo json_encode(['error' => 'No se pudo conectar con la API de Mokaná', 'detail' => $error]);
            exit;
        }

        http_response_code($status > 0 ? $status : 200);
        echo $response;
        exit;
    }
}
