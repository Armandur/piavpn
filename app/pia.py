import random
import socket
from pathlib import Path

from .config import settings


def list_regions() -> list[str]:
    configs_dir = Path(settings.configs_dir)
    return sorted(p.stem for p in configs_dir.glob("*.ovpn") if p.stem != "active")


def _read_config(region: str) -> str:
    path = Path(settings.configs_dir) / f"{region}.ovpn"
    if not path.exists():
        raise ValueError(f"Region '{region}' finns inte. Kör GET /regions.")
    return path.read_text()


def _extract_remote(content: str) -> tuple[str, str]:
    for line in content.splitlines():
        if line.lower().startswith("remote "):
            parts = line.split()
            if len(parts) >= 3:
                return parts[1], parts[2]
    raise ValueError("Ingen 'remote'-rad hittades i konfigfilen.")


def resolve_ips(region: str) -> list[str]:
    content = _read_config(region)
    hostname, _ = _extract_remote(content)
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ips = list({r[4][0] for r in results})
        random.shuffle(ips)
        return ips
    except socket.gaierror as e:
        raise RuntimeError(f"DNS-uppslag misslyckades for {hostname}: {e}") from e


def pick_server(region: str, used_ips: set[str], fresh: bool = False) -> tuple[str, str]:
    """Returnerar (ip, port) for en PIA-server i regionen."""
    content = _read_config(region)
    _, port = _extract_remote(content)
    ips = resolve_ips(region)

    if fresh:
        available = [ip for ip in ips if ip not in used_ips]
        if not available:
            raise RuntimeError(
                f"Alla IP:n i '{region}' ar anvanda ({len(used_ips)} st). "
                "Nollstall med DELETE /used eller byt region."
            )
        return available[0], port

    return ips[0], port


def build_config(region: str, target_ip: str) -> str:
    """Bygger openvpn-config med exakt en specificerad server-IP."""
    content = _read_config(region)
    lines: list[str] = []
    remote_written = False

    for line in content.splitlines():
        lower = line.lower().strip()
        if lower.startswith("remote "):
            if not remote_written:
                parts = line.split()
                port = parts[2] if len(parts) >= 3 else "1198"
                proto_suffix = f" {parts[3]}" if len(parts) >= 4 else ""
                lines.append(f"remote {target_ip} {port}{proto_suffix}")
                remote_written = True
            # Hoppar over extra remote-rader (PIA-filer har bara en)
        else:
            lines.append(line)

    return "\n".join(lines)
