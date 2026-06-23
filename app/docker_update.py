"""Optional Docker image pull + container restart (requires mounted socket)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.config import settings


def _docker_socket_path() -> Path:
    return Path(settings.docker_socket)


def watchtower_update_available() -> bool:
    """True when an immediate update can be triggered via the Watchtower HTTP API."""
    return bool((settings.watchtower_api_url or "").strip())


def update_apply_available() -> bool:
    if watchtower_update_available():
        return True
    if not settings.update_apply_enabled:
        return False
    return _docker_socket_path().is_socket()


async def trigger_watchtower_update() -> dict[str, str]:
    """Ask Watchtower (which holds docker.sock) to pull + recreate label-enabled containers."""
    url = (settings.watchtower_api_url or "").strip()
    if not url:
        raise RuntimeError("Watchtower API URL not configured")
    headers = {}
    token = (settings.watchtower_api_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"Watchtower API returned {resp.status_code}")
    return {"via": "watchtower", "status": "update-triggered"}


def _split_image_ref(image: str) -> tuple[str, str]:
    if "@" in image:
        image = image.split("@", 1)[0]
    if ":" in image.rsplit("/", 1)[-1]:
        repo, tag = image.rsplit(":", 1)
        return repo, tag
    return image, "latest"


async def pull_and_restart(image: str, container_name: str) -> dict[str, str]:
    socket = _docker_socket_path()
    if not socket.is_socket():
        raise RuntimeError("Docker socket not available")

    repo, tag = _split_image_ref(image)
    transport = httpx.AsyncHTTPTransport(uds=str(socket))
    async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=300.0) as client:
        pull = await client.post(
            "/images/create",
            params={"fromImage": repo, "tag": tag},
        )
        if pull.status_code >= 400:
            raise RuntimeError(f"Image pull failed ({pull.status_code})")

        filters = json.dumps({"name": [container_name]})
        listed = await client.get("/containers/json", params={"all": True, "filters": filters})
        if listed.status_code >= 400:
            raise RuntimeError("Could not list containers")
        containers = listed.json()
        if not containers:
            raise RuntimeError(f"Container '{container_name}' not found")

        container_id = containers[0]["Id"]
        restarted = await client.post(f"/containers/{container_id}/restart", params={"t": "10"})
        if restarted.status_code >= 400:
            raise RuntimeError(f"Container restart failed ({restarted.status_code})")

    return {"image": f"{repo}:{tag}", "container": container_name, "status": "restarted"}
