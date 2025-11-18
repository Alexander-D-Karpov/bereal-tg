# BeReal Telegram Bot

A Telegram bot that mimics BeReal functionality for group chats. The bot sends random daily notifications for members to share their photos.

## Features

- Random daily notifications in group chats
- Customizable time range
- Persistent storage with auto-save

## Setup

### Installation

1. Create `.env` file:
```bash
cp .env.example .env
```
2. Edit `.env` and add your bot token

3. Build and run with Docker Compose:
```bash
docker-compose up -d
```

### Local Development

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv sync
```

3. Run the bot:
```bash
uv run python -m bot.main
```

### Linting
```bash
uv run ruff check .
uv run ruff format .
```


## Usage

### User Commands

- `/register` - Register to receive photo reminders
- `/unregister` - Stop receiving photo reminders
- `/who` - List all registered users in the chat
- `/get_settings` - View current chat settings

### Admin Commands

- `/set_time_from HH:MM` - Set start time in MSK
- `/set_time_to HH:MM` - Set end time in MSK
- `/set_message <text>` - Set custom reminder message

### Example Workflow

1. Add the bot to your group chat
2. Users register with `/register`
3. Admin configures the bot:
```
/set_time_from 09:00
/set_time_to 21:00
/set_message Отправляйте свои фотки!
```
4. Bot will send notifications to registered users at random times

The bot will send a notification at a random time between 9:00 and 21:00 MSK each day.

## License

MIT