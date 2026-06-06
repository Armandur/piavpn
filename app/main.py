import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from .config import settings
from .pia import list_regions
from .vpn import manager, state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_tinyproxy: subprocess.Popen | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tinyproxy

    _tinyproxy = subprocess.Popen(
        ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("tinyproxy startad (pid %d, port %d)", _tinyproxy.pid, settings.proxy_port)

    try:
        await manager.connect(settings.pia_region)
    except Exception as e:
        logger.error("VPN-anslutning misslyckades vid start: %s", e)

    yield

    await manager.stop()

    if _tinyproxy:
        _tinyproxy.terminate()
        try:
            _tinyproxy.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _tinyproxy.kill()


app = FastAPI(title="piavpn", lifespan=lifespan)


@app.get("/status")
async def status():
    tp_ok = _tinyproxy is not None and _tinyproxy.poll() is None
    return {
        "vpn": "up" if state.connected else "down",
        "region": state.region,
        "ip": state.current_ip,
        "up_since": state.up_since.isoformat() if state.up_since else None,
        "proxy": "up" if tp_ok else "down",
    }


@app.get("/ip", response_class=PlainTextResponse)
async def get_ip():
    if not state.connected or not state.current_ip:
        raise HTTPException(503, "VPN är inte uppe")
    return state.current_ip


@app.post("/rotate")
async def rotate(fresh: bool = False):
    if not state.region:
        raise HTTPException(400, "Ingen region konfigurerad")
    try:
        ip = await manager.connect(state.region, fresh=fresh)
        return {"ip": ip, "fresh": fresh}
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.post("/region/{name}")
async def change_region(name: str):
    if name not in list_regions():
        raise HTTPException(404, f"Region '{name}' finns inte. Se GET /regions.")
    try:
        ip = await manager.connect(name)
        return {"region": name, "ip": ip}
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/used")
async def get_used():
    return {"used": sorted(state.used_ips), "count": len(state.used_ips)}


@app.delete("/used")
async def clear_used():
    count = len(state.used_ips)
    state.used_ips.clear()
    return {"cleared": count}


@app.get("/regions")
async def get_regions():
    return {"regions": list_regions()}
