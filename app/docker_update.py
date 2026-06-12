"""Optional Docker image pull + container restart (requires mounted socket)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.config import settings


def _docker_socket_path() -> Path:
    return Path(settings.docker_socket)


def update_apply_available() -> bool:
    if not settings.update_apply_enabled:
        return False
    return _docker_socket_path().is_socket()


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
