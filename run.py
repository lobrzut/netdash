import logging
import os

import uvicorn

from app.config import DEFAULT_LISTEN_PORT, FORBIDDEN_LISTEN_PORT, resolve_listen_port

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("netdash")

if __name__ == "__main__":
    legacy = os.environ.get("NETDASH_PORT", "").strip()
    if legacy:
        logger.error(
            "NETDASH_PORT=%s is ignored (stale QNAP CS); use NETDASH_LISTEN_PORT only",
            legacy,
        )

    port = resolve_listen_port()
    if port == FORBIDDEN_LISTEN_PORT:
        logger.error(
            "Refusing to bind port %s (Readarr conflict); forcing %s",
            FORBIDDEN_LISTEN_PORT,
            DEFAULT_LISTEN_PORT,
        )
        port = DEFAULT_LISTEN_PORT

    logger.info("LISTEN_PORT=%s (8787 blocked)", port)
    logger.info("NetDash listening on port %s", port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
