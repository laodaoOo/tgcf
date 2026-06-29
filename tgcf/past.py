"""The module for running tgcf in past mode.

- past mode can only operate with a user account.
- past mode deals with all existing messages.
"""

import asyncio
import logging
import os
import time

# --- 新增引入 socks 库 ---
import socks
# ------------------------

from telethon import TelegramClient
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.custom.message import Message
from telethon.tl.patched import MessageService

from tgcf import config
from tgcf import storage as st
from tgcf.config import CONFIG, get_SESSION, write_config
from tgcf.plugins import apply_plugins, load_async_plugins
from tgcf.utils import clean_session_files, send_message


async def forward_job() -> None:
    """Forward all existing messages in the concerned chats."""
    clean_session_files()

    # load async plugins defined in plugin_models
    await load_async_plugins()  

    if CONFIG.login.user_type != 1:
        logging.warning(
            "You cannot use bot account for tgcf past mode. Telegram does not allow bots to access chat history."
        )
        return
    
    SESSION = get_SESSION()

    # --- 新增：从 .env 或环境变量中读取代理配置 ---
    proxy_ip = os.getenv("TGCF_PROXY_IP")
    proxy_port = os.getenv("TGCF_PROXY_PORT")
    proxy_type_str = os.getenv("TGCF_PROXY_TYPE", "SOCKS5").upper()
    
    proxy_config = None
    if proxy_ip and proxy_port:
        proxy_type = socks.SOCKS5 if proxy_type_str == "SOCKS5" else socks.HTTP
        proxy_config = (proxy_type, proxy_ip, int(proxy_port))
        logging.info(f"Proxy enabled in past mode: {proxy_type_str} {proxy_ip}:{proxy_port}")
    else:
        logging.info("No proxy configured in .env, running directly in past mode.")
    # ---------------------------------------------

    async with TelegramClient(
        SESSION, 
        CONFIG.login.API_ID, 
        CONFIG.login.API_HASH,
        proxy=proxy_config  # --- 新增：将代理配置传入 Client ---
    ) as client:
        config.from_to = await config.load_from_to(client, config.CONFIG.forwards)
        client: TelegramClient
        for from_to, forward in zip(config.from_to.items(), config.CONFIG.forwards):
            src, dest = from_to
            last_id = 0
            forward: config.Forward
            logging.info(f"Forwarding messages from {src} to {dest}")
            async for message in client.iter_messages(
                src, reverse=True, offset_id=forward.offset
            ):
                message: Message
                event = st.DummyEvent(message.chat_id, message.id)
                event_uid = st.EventUid(event)

                if forward.end and last_id > forward.end:
                    continue
                if isinstance(message, MessageService):
                    continue
                try:
                    tm = await apply_plugins(message)
                    if not tm:
                        continue
                    st.stored[event_uid] = {}

                    if message.is_reply:
                        r_event = st.DummyEvent(
                            message.chat_id, message.reply_to_msg_id
                        )
                        r_event_uid = st.EventUid(r_event)
                    for d in dest:
                        if message.is_reply and r_event_uid in st.stored:
                            tm.reply_to = st.stored.get(r_event_uid).get(d)
                        fwded_msg = await send_message(d, tm)
                        st.stored[event_uid].update({d: fwded_msg.id})
                    tm.clear()
                    last_id = message.id
                    logging.info(f"forwarding message with id = {last_id}")
                    forward.offset = last_id
                    write_config(CONFIG, persist=False)
                    time.sleep(CONFIG.past.delay)
                    logging.info(f"slept for {CONFIG.past.delay} seconds")

                except FloodWaitError as fwe:
                    logging.info(f"Sleeping for {fwe}")
                    await asyncio.sleep(delay=fwe.seconds)
                except Exception as err:
                    logging.exception(err)
