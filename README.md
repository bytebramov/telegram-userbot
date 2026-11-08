# Telegram Userbot

Python + Telethon starter.

## Features
- `.sms <count> <interval> <message>` schedules repeated messages in the current chat.
- `.stop` cancels the schedule.
- `.status` reports schedule state.
- `.addchat [id]` adds a chat to the repost list (current chat if no id given).
- `.delchat [id]` removes a chat from the repost list.
- `.chats` lists chats currently in the repost list.
- `.repost` (as a reply to a message) forwards that message to every chat in the repost list.
- One Telegram session and conservative rate limits.

Use only in chats where you have permission to automate messages. Not for unsolicited or bulk messaging.

## Setup
1. Install Python 3.11+.
2. Run `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in Telegram API credentials from https://my.telegram.org.
4. Run `python main.py` and authenticate in the terminal.

## Commands
- `.sms 3 1m Hello!` — send Hello! three times, one minute apart.
- `.sms 2 30s Test` — send twice, 30 seconds apart.
- `.stop` — cancel.
- `.status` — status.
- `.addchat` — add the current chat to the repost list.
- `.addchat 123456789` — add a chat by id.
- `.delchat` / `.delchat 123456789` — remove a chat from the list.
- `.chats` — show the repost list.
- `.repost` — reply to any message with this to forward it to every chat in the repost list (5s pause between sends; waits out any `FloodWaitError` from Telegram automatically).

Intervals: s=seconds, m=minutes, h=hours, d=days. Limits: 1–5 messages per `.sms` run, minimum 20 seconds between repeats, one active schedule per chat.

The repost list is stored locally in `chats.json` (git-ignored, created automatically on first `.addchat`). Your account must already be a member of every chat in that list — `.repost` can't reach chats it hasn't joined.

Never commit `.env`, Telegram session files (`*.session`), `chats.json`, or login codes. Keep your session private — it grants full account access, same as your password.
