# Telegram Userbot

Python + Telethon starter.

## Features
- `.sms <count> <interval> <message>` schedules repeated messages in the current chat.
- `.stop` cancels the schedule.
- `.status` reports schedule state.
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

Intervals: s=seconds, m=minutes, h=hours, d=days. Starter limits: 1–5 messages, minimum 60 seconds, one active schedule per chat.

Never commit `.env`, Telegram session files, or login codes. Keep your session private.
