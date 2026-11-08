import asyncio
import json
import logging
import os
import re

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

logging.basicConfig(level=logging.INFO)
logging.getLogger("telethon").setLevel(logging.WARNING)
log = logging.getLogger("telegram-userbot")

INTERVAL_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
MAX_MESSAGES = 5
MIN_INTERVAL_SECONDS = 20
REPOST_DELAY_SECONDS = 5  # pause between sends to different chats in one .repost run

ACCOUNTS_FILE = "accounts.json"


def load_accounts() -> list[dict]:
    """
    accounts.json format:
    [
      {"name": "acc1", "api_id": 123456, "api_hash": "abc...", "session": "acc1"},
      {"name": "acc2", "api_id": 123456, "api_hash": "abc...", "session": "acc2"}
    ]
    api_id/api_hash can be the same for every account, or different per account
    if you created separate apps on my.telegram.org — both work.
    """
    if not os.path.exists(ACCOUNTS_FILE):
        raise SystemExit(
            f"{ACCOUNTS_FILE} not found. Create it with a list of accounts, "
            f"each with name, api_id, api_hash and session. See README."
        )
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as fh:
        accounts = json.load(fh)
    if not isinstance(accounts, list) or not accounts:
        raise SystemExit(f"{ACCOUNTS_FILE} must contain a non-empty list of accounts.")

    seen_sessions = set()
    for acc in accounts:
        missing = [k for k in ("name", "api_id", "api_hash", "session") if k not in acc]
        if missing:
            raise SystemExit(f"Account entry {acc} is missing fields: {missing}")
        if acc["session"] in seen_sessions:
            raise SystemExit(f"Duplicate session name: {acc['session']}")
        seen_sessions.add(acc["session"])
    return accounts


def load_chats(chats_file: str) -> list[int]:
    if not os.path.exists(chats_file):
        return []
    try:
        with open(chats_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [int(x) for x in data]
    except (json.JSONDecodeError, ValueError, OSError):
        log.exception("Failed to read %s", chats_file)
        return []


def save_chats(chats_file: str, chats: list[int]) -> None:
    with open(chats_file, "w", encoding="utf-8") as fh:
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


def build_client(account: dict) -> TelegramClient:
    """Create a TelegramClient and register all command handlers for one account."""
    name = account["name"]
    chats_file = f"chats_{account['session']}.json"
    client = TelegramClient(account["session"], int(account["api_id"]), account["api_hash"])
    active_tasks: dict[int, asyncio.Task] = {}

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
                log.exception("[%s] Scheduled sending failed", name)
            finally:
                active_tasks.pop(event.chat_id, None)

        active_tasks[event.chat_id] = asyncio.create_task(scheduled_sender())

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.addchat(\s+.+)?$"))
    async def addchat_handler(event):
        arg = (event.pattern_match.group(1) or "").strip()
        target_id = int(arg) if arg else event.chat_id

        chats = load_chats(chats_file)
        if target_id in chats:
            await event.reply("This chat is already in the repost list.")
            return
        chats.append(target_id)
        save_chats(chats_file, chats)
        await event.reply(f"Added `{target_id}` to the repost list ({len(chats)} total).")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.delchat(\s+.+)?$"))
    async def delchat_handler(event):
        arg = (event.pattern_match.group(1) or "").strip()
        target_id = int(arg) if arg else event.chat_id

        chats = load_chats(chats_file)
        if target_id not in chats:
            await event.reply("That chat isn't in the repost list.")
            return
        chats.remove(target_id)
        save_chats(chats_file, chats)
        await event.reply(f"Removed `{target_id}` from the repost list ({len(chats)} total).")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.chats$"))
    async def chats_handler(event):
        chats = load_chats(chats_file)
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

        chats = load_chats(chats_file)
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
                log.warning("[%s] Flood wait %ss while reposting to %s", name, exc.seconds, chat_id)
                failed.append(chat_id)
                await asyncio.sleep(exc.seconds)
            except Exception:
                log.exception("[%s] Failed to repost to %s", name, chat_id)
                failed.append(chat_id)
            await asyncio.sleep(REPOST_DELAY_SECONDS)

        summary = f"Done: {sent}/{len(chats)} sent."
        if failed:
            summary += f" Failed: {', '.join(str(c) for c in failed)}."
        await status.edit(summary)

    return client


async def run_account(account: dict) -> None:
    client = build_client(account)
    await client.start()
    me = await client.get_me()
    log.info("[%s] Logged in as %s. Keep your session file private.",
              account["name"], me.username or me.id)
    await client.run_until_disconnected()


async def main():
    accounts = load_accounts()
    log.info("Starting %d account(s): %s", len(accounts), ", ".join(a["name"] for a in accounts))
    await asyncio.gather(*(run_account(acc) for acc in accounts))


if __name__ == "__main__":
    asyncio.run(main())
