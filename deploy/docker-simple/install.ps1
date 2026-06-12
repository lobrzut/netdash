# NetDash — prosty deploy na Windows (Docker Desktop + Linux containers)

#   irm https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.ps1 | iex

$ErrorActionPreference = "Stop"



$InstallDir = if ($env:NETDASH_INSTALL_DIR) { $env:NETDASH_INSTALL_DIR } else { "$env:USERPROFILE\netdash" }

$RepoRaw = "https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple"



if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {

    Write-Error "Brak Docker. Zainstaluj Docker Desktop (Linux containers)."

}



New-Item -ItemType Directory -Force -Path "$InstallDir\data" | Out-Null

Set-Location $InstallDir



Write-Host "-> Pobieram pliki z GitHub..." -ForegroundColor Cyan

Invoke-WebRequest -Uri "$RepoRaw/docker-compose.yml" -OutFile "docker-compose.yml" -UseBasicParsing

Invoke-WebRequest -Uri "$RepoRaw/docker-compose.autoupdate.yml" -OutFile "docker-compose.autoupdate.yml" -UseBasicParsing

Invoke-WebRequest -Uri "$RepoRaw/.env.example" -OutFile ".env.example" -UseBasicParsing



if (-not (Test-Path ".env")) {

    $secretKey = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 })) -replace '[^a-zA-Z0-9]', ''

    $secretKey = $secretKey.Substring(0, [Math]::Min(43, $secretKey.Length))

    @"

NETDASH_SECRET_KEY=$secretKey

NETDASH_DEFAULT_ADMIN_PASSWORD=changeme
NETDASH_DEFAULT_ADMIN_USER=admin
NETDASH_SYNC_ADMIN_PASSWORD=true

NETDASH_SCAN_CIDR=192.168.1.0/24

"@ | Set-Content -Encoding utf8 ".env"

    Write-Host "-> Utworzono .env (login: admin / changeme — zmien haslo po pierwszym logowaniu)" -ForegroundColor Green

} else {

    Write-Host "-> .env juz istnieje — pomijam" -ForegroundColor Yellow

}



Write-Host "-> Pobieram obraz z GHCR..." -ForegroundColor Cyan

docker compose pull



Write-Host "-> Uruchamiam NetDash..." -ForegroundColor Cyan

docker compose up -d



Write-Host ""

$port = if ($env:NETDASH_LISTEN_PORT) { $env:NETDASH_LISTEN_PORT } else { "18787" }

Write-Host "NetDash -> http://localhost:$port" -ForegroundColor Green

Write-Host "Login: admin / changeme (zmien w Ustawienia -> Haslo)"

Write-Host "Dane: $InstallDir\data"

