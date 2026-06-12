# NetDash — agent zdalnego discovery

Lekki agent skanuje LAN na hoście z pełnym dostępem do sieci (np. homelab **192.168.1.201**) i wysyła wyniki do NetDash na QNAP (**192.168.1.150**) przez `POST /api/discovery/import`.

## Wymagania

- Docker z `network_mode: host` (lub uruchom `scripts/netdash-agent.py` bezpośrednio na hoście Linux)
- NetDash z **v1.3.112+** i `NETDASH_SCAN_DISABLED=true` na dashboardzie (QNAP)

## Szybki start (.201)

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
| `INTERVAL` | `300` | Sekundy między skanami (`0` lub `--once` = jeden raz) |
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
