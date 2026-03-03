from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.config import Config
from app.gemini_api import GeminiAPI
from app.router import BotRouter
from app.storage import DialogStorage
from app.telegram_api import TelegramAPI


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Prevent tokens and API keys from appearing in low-level HTTP request logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return logging.getLogger("medibot")


def build_http_client(config: Config) -> httpx.Client:
    timeout = httpx.Timeout(
        connect=20.0,
        read=float(config.poll_timeout_sec + 15),
        write=20.0,
        pool=20.0,
    )
    return httpx.Client(timeout=timeout, proxy=config.proxy_url)


def process_updates_once(
    telegram: TelegramAPI,
    router: BotRouter,
    offset: Optional[int],
    timeout: int,
    logger: logging.Logger,
) -> Optional[int]:
    updates = telegram.get_updates(offset=offset, timeout=timeout)
    next_offset = offset
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            next_offset = update_id + 1
        try:
            router.handle_update(update)
        except Exception:
            logger.exception("Failed to process update: %s", update)
    return next_offset


def run() -> None:
    logger = setup_logging()
    config = Config.from_env()
    logger.info("Starting bot with model: %s", config.gemini_model)

    with build_http_client(config) as http_client:
        telegram = TelegramAPI(config.telegram_bot_token, http_client)
        gemini = GeminiAPI(config.gemini_api_key, config.gemini_model, http_client)
        storage = DialogStorage(config.sqlite_path)
        router = BotRouter(telegram, gemini, storage, config, logger)

        offset: Optional[int] = None
        while True:
            try:
                offset = process_updates_once(
                    telegram=telegram,
                    router=router,
                    offset=offset,
                    timeout=config.poll_timeout_sec,
                    logger=logger,
                )
            except Exception:
                logger.exception(
                    "Polling error. Retrying in %.2f sec.", config.poll_retry_delay_sec
                )
                time.sleep(config.poll_retry_delay_sec)


if __name__ == "__main__":
    run()
