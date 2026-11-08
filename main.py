import asyncio
import json
import logging
import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

load_dotenv()
logging.basicConfig(level=logging.INFO)
logging.getLogger("telethon").setLevel(logging.WARNING)
log = logging.getLogger("telegram-userbot")

api_id = os.getenv("TG_API_ID", "").strip()
api_hash = os.getenv("TG_API_HASH", "").strip()
session_name = os.getenv("TG_SESSION", "telegram_userbot")

if not api_id.isdigit() or not api_hash:
    raise SystemExit("Set TG_API_ID and TG_API_HASH in your .env file.")

client = TelegramClient(session_name, int(api_id), api_hash)
active_tasks: dict[int, asyncio.Task] = {}

INTERVAL_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
MAX_MESSAGES = 5
MIN_INTERVAL_SECONDS = 20

CHATS_FILE = os.getenv("TG_CHATS_FILE", "chats.json")
REPOST_DELAY_SECONDS = 5  # pause between sends to different chats in one .repost run


def load_chats() -> list[int]:
    if not os.path.exists(CHATS_FILE):
        return []
    try:
        with open(CHATS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [int(x) for x in data]
    except (json.JSONDecodeError, ValueError, OSError):
        log.exception("Failed to read %s", CHATS_FILE)
        return []


def save_chats(chats: list[int]) -> None:
    with open(CHATS_FILE, "w", encoding="utf-8") as fh:
        json.dump(chats, fh, indent=2)


def parse_interval(value: str) -> int:
    match = INTERVAL_RE.fullmatch(value)
    if not match:
        raise ValueError("Interval must look like 30s, 5m, 2h or 1d.")
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if amount < 1:
        raise ValueError("Interval must be positive.")
    seconds = amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    if seconds < MIN_INTERVAL_SECONDS:
        raise ValueError(f"Minimum interval is {MIN_INTERVAL_SECONDS} seconds.")
    return seconds


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.stop$"))
async def stop_handler(event):
    task = active_tasks.get(event.chat_id)
    if task and not task.done():
        task.cancel()
        await event.reply("Schedule cancelled.")
    else:
        await event.reply("No active schedule in this chat.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.status$"))
async def status_handler(event):
    task = active_tasks.get(event.chat_id)
    await event.reply("A schedule is running." if task and not task.done()
                      else "No active schedule in this chat.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.sms\s+"))
async def sms_handler(event):
    # Format: .sms <count> <interval> <message>
    parts = event.raw_text.strip().split(maxsplit=3)
    if len(parts) != 4:
        await event.reply("Usage: .sms <1-5> <interval> <message>\nExample: .sms 3 1m Hello!")
        return

    try:
        count = int(parts[1])
        interval = parse_interval(parts[2])
    except ValueError as exc:
        await event.reply(str(exc))
        return

    message = parts[3].strip()
    if not 1 <= count <= MAX_MESSAGES:
        await event.reply(f"Count must be between 1 and {MAX_MESSAGES}.")
        return
    if not message or len(message) > 1000:
        await event.reply("Message must contain 1–1000 characters.")
        return

    old_task = active_tasks.get(event.chat_id)
    if old_task and not old_task.done():
        await event.reply("Schedule already running here. Use .stop first.")
        return

    await event.delete()

    async def scheduled_sender():
        try:
            for _ in range(count):
                await asyncio.sleep(interval)
                await client.send_message(event.chat_id, message)
            await client.send_message(event.chat_id, "Schedule finished.")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scheduled sending failed")
        finally:
            active_tasks.pop(event.chat_id, None)

    active_tasks[event.chat_id] = asyncio.create_task(scheduled_sender())


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.addchat(\s+.+)?$"))
async def addchat_handler(event):
    # .addchat          -> adds the current chat
    # .addchat <id>     -> adds an arbitrary chat by id
    arg = (event.pattern_match.group(1) or "").strip()
    target_id = int(arg) if arg else event.chat_id

    chats = load_chats()
    if target_id in chats:
        await event.reply("This chat is already in the repost list.")
        return
    chats.append(target_id)
    save_chats(chats)
    await event.reply(f"Added `{target_id}` to the repost list ({len(chats)} total).")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.delchat(\s+.+)?$"))
async def delchat_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    target_id = int(arg) if arg else event.chat_id

    chats = load_chats()
    if target_id not in chats:
        await event.reply("That chat isn't in the repost list.")
        return
    chats.remove(target_id)
    save_chats(chats)
    await event.reply(f"Removed `{target_id}` from the repost list ({len(chats)} total).")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.chats$"))
async def chats_handler(event):
    chats = load_chats()
    if not chats:
        await event.reply("Repost list is empty. Add chats with .addchat")
        return
    listing = "\n".join(f"- `{c}`" for c in chats)
    await event.reply(f"Repost list ({len(chats)}):\n{listing}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.repost$"))
async def repost_handler(event):
    reply_msg = await event.get_reply_message()
    if reply_msg is None:
        await event.reply("Reply to the post you want to repost with .repost")
        return

    chats = load_chats()
    if not chats:
        await event.reply("Repost list is empty. Add chats with .addchat first.")
        return

    status = await event.reply(f"Reposting to {len(chats)} chat(s)...")

    sent, failed = 0, []
    for chat_id in chats:
        try:
            await client.forward_messages(chat_id, messages=reply_msg)
            sent += 1
        except FloodWaitError as exc:
            log.warning("Flood wait %ss while reposting to %s", exc.seconds, chat_id)
            failed.append(chat_id)
            await asyncio.sleep(exc.seconds)
        except Exception:
            log.exception("Failed to repost to %s", chat_id)
            failed.append(chat_id)
        await asyncio.sleep(REPOST_DELAY_SECONDS)

    summary = f"Done: {sent}/{len(chats)} sent."
    if failed:
        summary += f" Failed: {', '.join(str(c) for c in failed)}."
    await status.edit(summary)


async def main():
    await client.start()
    me = await client.get_me()
    log.info("Logged in as %s. Keep your session file private.", me.username or me.id)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
