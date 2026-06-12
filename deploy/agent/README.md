# NetDash — opcjonalny agent zdalnego discovery

> **Od v1.3.117:** QNAP z `NETDASH_DISCOVERY_MODE=arp` skanuje LAN **lokalnie** (arp-scan, host network) — agent **nie jest wymagany** gdy NetDash działa na serwerze homelab (NAS).

Lekki agent skanuje LAN na **innym** hoście z pełnym dostępem do sieci i wysyła wyniki do NetDash przez `POST /api/discovery/import`. Przydatny gdy dashboard jest na QNAP w trybie bridge bez host mode, lub discovery ma działać z PC/VM.

## Wymagania

- Docker z `network_mode: host` (lub uruchom `scripts/netdash-agent.py` bezpośrednio na hoście Linux)
- NetDash z **v1.3.112+**; tryb `NETDASH_DISCOVERY_MODE=remote` + `NETDASH_SCAN_DISABLED=true` na dashboardzie

## Szybki start (.201)

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/agent/install.sh | NETDASH_PASSWORD=twoje-haslo bash
```

Lub ręcznie:

```bash
cd deploy/agent
export NETDASH_URL=http://192.168.1.150:18787
export NETDASH_USER=admin
export NETDASH_PASSWORD=twoje-haslo
export SCAN_CIDR=192.168.1.0/24
docker compose up -d --build
```

Jednorazowy skan (test):

```bash
docker compose run --rm netdash-agent python3 /agent/netdash-agent.py --once
```

## Zmienne środowiskowe

| Zmienna | Domyślnie | Opis |
|---------|-----------|------|
| `NETDASH_URL` | `http://127.0.0.1:18787` | URL portalu NetDash |
| `NETDASH_TOKEN` | — | Bearer JWT (opcjonalnie, zamiast loginu) |
| `NETDASH_USER` | `admin` | Login do `/api/auth/login` |
| `NETDASH_PASSWORD` | — | Hasło |
| `SCAN_CIDR` | `192.168.1.0/24` | Sieć do skanu |
| `INTERVAL` | `600` | Sekundy między skanami (domyślnie co 10 min) |
| `MARK_MISSING_OFFLINE` | `true` | Oznacz brakujące hosty jako offline |
| `AGENT_HOSTNAME` | hostname OS | Widoczne w portalu jako źródło importu |

## Metody skanu (kolejność)

1. **arp-scan** — `--interval=100ms --retry=1` (rate-limited)
2. **ip neigh** — pasywna tabela sąsiadów
3. **ping sweep** — fallback gdy brak arp-scan

## Bez Dockera

```bash
pip install  # brak zależności Python poza stdlib
sudo apt install arp-scan iproute2 iputils-ping
export NETDASH_URL=http://192.168.1.150:18787 NETDASH_PASSWORD=...
python3 scripts/netdash-agent.py --once
```
