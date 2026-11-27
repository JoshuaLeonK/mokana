@echo off
chcp 65001 >nul
echo ============================================================
echo   MOKANA - Prueba en vivo contra API Bot Agente IA
echo   Endpoint: https://mokana.joshual.tech/api/reports
echo ============================================================
echo.
echo Enviando reporte de prueba (Cienaga de Mallorquin)...
echo.

curl.exe -s -X POST "https://mokana.joshual.tech/api/reports" ^
  -H "Content-Type: application/json" ^
  -d "{\"zone_id\":\"zone_mallorquin\",\"category_id\":\"alert_color\",\"description\":\"Prueba de monitoreo Mokana: espuma densa y manchas oscuras en borde de mangle rojo cerca del puente.\",\"lat\":11.0458,\"lng\":-74.8461,\"citizen_name\":\"Prueba Mokana BAT\",\"citizen_phone\":\"+573001501565\"}"

echo.
echo.
echo ============================================================
echo   Listo. Verifica en tu navegador (http://localhost:4175)
echo   que la alerta aparecio en vivo en Dashboard y Gestion de Alertas.
echo ============================================================
pause
