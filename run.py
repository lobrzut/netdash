import logging

import uvicorn

from app.config import resolve_listen_port

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("netdash")

if __name__ == "__main__":
    port = resolve_listen_port()
    legacy = __import__("os").environ.get("NETDASH_PORT", "").strip()
    if legacy == "8787":
        logger.warning(
            "Ignoring NETDASH_PORT=8787 (Readarr conflict); listening on %s",
            port,
        )
    logger.info("NetDash listening on port %s", port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
