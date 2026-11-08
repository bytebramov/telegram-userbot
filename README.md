# Telegram Userbot

Python + Telethon starter. Supports running one or several Telegram accounts
from a single process.

## Features
- Multi-account: run any number of accounts in one process, each with its own
  command handlers and its own repost list.
- `.sms <count> <interval> <message>` schedules repeated messages in the current chat.
- `.stop` cancels the schedule.
- `.status` reports schedule state.
- `.addchat [id]` adds a chat to that account's repost list (current chat if no id given).
- `.delchat [id]` removes a chat from that account's repost list.
- `.chats` lists chats currently in that account's repost list.
- `.repost` (as a reply to a message) forwards that message to every chat in
  that account's repost list.

Use only in chats where you have permission to automate messages. Not for unsolicited or bulk messaging.

## Setup
1. Install Python 3.11+.
2. Run `python -m pip install -r requirements.txt`.
3. Copy `accounts.json.example` to `accounts.json` and fill in one entry per
   account you want to run:
   ```json
   [
     {"name": "acc1", "api_id": 12345678, "api_hash": "your_hash", "session": "acc1"},
     {"name": "acc2", "api_id": 12345678, "api_hash": "your_hash", "session": "acc2"}
   ]
Get api_id/api_hash from https://my.telegram.org/apps — you can reuse
the same app credentials for every account, or create a separate app per
account. Either works.
session is the filename Telethon stores that account's login under
(<session>.session). It must be unique per account.
name is just a label used in the logs.
Run python main.py. It starts one login per account in order — enter each
phone number and code as prompted, one after another, the first time.
Commands
Each account listens for these commands independently, in whatever chats that
account's own user is in:
.sms 3 1m Hello! — send Hello! three times, one minute apart.
.sms 2 30s Test — send twice, 30 seconds apart.
.stop — cancel a running .sms schedule in this chat.
.status — check schedule state in this chat.
.addchat — add the current chat to this account's repost list.
.addchat 123456789 — add a chat by id.
.delchat / .delchat 123456789 — remove a chat from the list.
.chats — show this account's repost list.
.repost — reply to any message with this to forward it to every chat in
this account's repost list (5s pause between sends; waits out any
FloodWaitError from Telegram automatically).
Intervals: s=seconds, m=minutes, h=hours, d=days. Limits: 1–5 messages per
.sms run, minimum 20 seconds between repeats, one active schedule per chat
per account.
Each account's repost list is stored locally in chats_<session>.json
(git-ignored, created automatically on first .addchat). An account must
already be a member of every chat in its own list — .repost can't reach
chats that account hasn't joined.
Never commit accounts.json, Telegram session files (*.session),
chats_*.json, or login codes. Keep your session files private — each one
grants full access to that account, same as its password.
