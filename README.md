# piavpn

PIA VPN-proxy med HTTP-triggad in-process-rotation. En container med openvpn +
tinyproxy + FastAPI-kontrollserver. Rotation sker in-process (~5-10s) utan
container-restart, till skillnad från gluetun-varianten i `piahttpsproxy`.

## Innehall

- **openvpn** - ansluter mot en DNS-resolvad PIA-server
- **tinyproxy** - HTTP-proxy pa port 8888
- **FastAPI** - kontrollserver pa port 8000

## Kom igang

```bash
cp .env.example .env
# Fyll i PIA_USER och PIA_PASS

docker compose up -d --build
```

Configs laddas ned automatiskt vid forsta start. Efterfoljande starter anvander
den persisterade volymen.

## Anvandning fran Python

```python
import requests

CTRL = "http://127.0.0.1:8000"
PROXY = {"http": "http://127.0.0.1:8888", "https": "http://127.0.0.1:8888"}

# Garanterat oanvand IP
requests.post(f"{CTRL}/rotate", params={"fresh": "true"})
print(requests.get("https://ipinfo.io/json", proxies=PROXY).json()["ip"])

# Nollstall branda IPs nar du vill borja om
requests.delete(f"{CTRL}/used")
```

## API

| Metod  | Endpoint          | Funktion                                          |
|--------|-------------------|---------------------------------------------------|
| GET    | `/status`         | VPN-status, region, IP, proxy-status              |
| GET    | `/ip`             | Nuvarande publik exit-IP (plain text)             |
| POST   | `/rotate`         | Ny IP (`?fresh=true` = garanterat oanvand)        |
| POST   | `/region/{name}`  | Byt region och koppla om                          |
| GET    | `/used`           | Lista branda IP:n denna session                   |
| DELETE | `/used`           | Nollstall branda IP:n                             |
| GET    | `/regions`        | Lista tillgangliga regioner                       |

## Flera instanser

Varje projekt som behover isolerad rotation kor en egen instans med unika portar:

```bash
# Projekt B: portar 8891/8003
PROXY_PORT=8891 CONTROL_PORT=8003 docker compose -p proj_b up -d
```

eller med separat `.env`:

```env
PROXY_PORT=8891
CONTROL_PORT=8003
```

## Kill-switch

iptables-regler satter sig vid start och blockerar all utgaende trafik utom:
- OpenVPN-anslutningen till PIA:s servrar (UDP/TCP 1194, 1198, 501, 502)
- All trafik via tun-interfacet (tunneln)
- Loopback (Docker-intern DNS pa 127.0.0.11)
- Inkommande anslutningar till portarna 8000 och 8888

Om VPN-tunneln faller begar tinyproxy-anslutningar timeout istallet for att
laka okrypterad trafik.

## Miljovariabler

| Variabel            | Default        | Beskrivning                        |
|---------------------|----------------|------------------------------------|
| `PIA_USER`          | (obligatorisk) | PIA-anvandarnamn                   |
| `PIA_PASS`          | (obligatorisk) | PIA-losenord                       |
| `PIA_REGION`        | `se_stockholm` | Startregion                        |
| `PIA_ENCRYPTION`    | `strong`       | `strong` eller `normal`            |
| `OPENVPN_PROTOCOL`  | `udp`          | `udp` eller `tcp`                  |
| `PROXY_PORT`        | `8888`         | Hostport for HTTP-proxy            |
| `CONTROL_PORT`      | `8000`         | Hostport for kontroll-API          |
