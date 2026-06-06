import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from .config import settings
from .pia import build_config, pick_server

logger = logging.getLogger(__name__)


@dataclass
class VpnState:
    region: str = ""
    current_ip: str = ""
    up_since: datetime | None = None
    used_ips: set[str] = field(default_factory=set)
    connected: bool = False


state = VpnState()


class VpnManager:
    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._config_path: str | None = None
        self._reader_task: asyncio.Task | None = None
        self._connected_event: asyncio.Event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def connect(self, region: str, fresh: bool = False) -> str:
        """Ansluter till VPN. Returnerar publik exit-IP."""
        async with self._lock:
            return await self._connect(region, fresh)

    async def _connect(self, region: str, fresh: bool) -> str:
        await self._stop()

        ip, port = pick_server(region, state.used_ips, fresh)
        logger.info("Ansluter till %s via %s:%s", region, ip, port)

        config = build_config(region, ip)

        fd, path = tempfile.mkstemp(suffix=".ovpn", prefix="piavpn_")
        try:
            os.write(fd, config.encode())
        finally:
            os.close(fd)
        self._config_path = path

        self._connected_event.clear()
        self._process = await asyncio.create_subprocess_exec(
            "openvpn",
            "--config", path,
            "--auth-user-pass", settings.auth_file,
            "--verb", "3",
            "--script-security", "2",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        self._reader_task = asyncio.create_task(self._read_output())

        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            await self._stop()
            raise RuntimeError("OpenVPN anslot inte inom 60 sekunder.")

        public_ip = await self._fetch_public_ip()

        state.region = region
        state.current_ip = public_ip
        state.up_since = datetime.now()
        state.connected = True
        state.used_ips.add(public_ip)

        logger.info("Ansluten. Publik IP: %s", public_ip)
        return public_ip

    async def _read_output(self) -> None:
        while self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            logger.debug("openvpn: %s", text)
            if "Initialization Sequence Completed" in text:
                self._connected_event.set()

        if state.connected:
            logger.warning("openvpn-processen avslutade oväntat")
            state.connected = False
            state.current_ip = ""
            state.up_since = None

    async def _fetch_public_ip(self) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(10):
                try:
                    r = await client.get("https://ipinfo.io/ip")
                    return r.text.strip()
                except Exception:
                    await asyncio.sleep(2)
        raise RuntimeError("Kunde inte hamta publik IP via tunneln efter 10 forsok.")

    async def stop(self) -> None:
        async with self._lock:
            await self._stop()

    async def _stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            self._process = None

        if self._config_path and os.path.exists(self._config_path):
            os.unlink(self._config_path)
            self._config_path = None

        state.connected = False
        state.current_ip = ""
        state.up_since = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None


manager = VpnManager()
