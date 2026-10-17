$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

Write-Host "Запуск основных сервисов..."
docker compose up -d postgres minio lakekeeper trino

if ($LASTEXITCODE -ne 0) {
    throw "Не удалось запустить Docker-сервисы."
}

Write-Host "Настройка MinIO и Lakekeeper..."
python scripts/setup.py

if ($LASTEXITCODE -ne 0) {
    throw "Не удалось создать bucket или warehouse."
}

Write-Host "Основные сервисы запущены, warehouse готов."
docker compose ps

if ($LASTEXITCODE -ne 0) {
    throw "Не удалось получить состояние Docker-сервисов."
}
