# Meal Bot

An AI-powered Telegram bot that tracks your meals by analyzing video notes using Google's Gemini models and logging the nutritional information directly into a Notion database.

## Features

- **Video Note Analysis**: Simply send a video note to the bot showing or describing your meal.
- **AI-Powered Nutrition Extraction**: Uses Google's Gemini (3.1 Flash Lite with resilient fallback capabilities) to detect multiple meal occasions, food items, and estimate macros (Protein, Carbs, Fat) and Calories.
- **Notion Integration**: Automatically logs every meal occasion as a structured entry in your Notion database.
- **Access Control**: Only authorized users can interact with the bot.
- **Resilient Pipeline**: Includes retry mechanisms for transient AI generation errors and an inline "Retry" button on Telegram if the pipeline occasionally fails.

## Prerequisites

- **Python 3.13+** or **Docker**
- [uv](https://github.com/astral-sh/uv) (recommended for local dependency management)
- **Telegram Bot Token**: Get one from [@BotFather](https://t.me/BotFather) on Telegram.
- **Gemini API Key**: Obtainable from [Google AI Studio](https://aistudio.google.com/).
- **Notion Integration Token**: Create an integration and get the token at [Notion Developers](https://www.notion.so/my-integrations).
- **Notion Database**: A Notion database with the following properties:
  - `Meal` (Title)
  - `Date` (Date)
  - `Calories` (Number)
  - `Protein (g)` (Number)
  - `Carbs (g)` (Number)
  - `Fat (g)` (Number)
  - `Meal Type` (Select: Breakfast, Lunch, Dinner, Snack)
  - `Food Items` (Multi-select)
  - `Notes` (Text / Rich Text)

>*Make sure your Notion Integration has been invited/granted access to the database you plan to use.*

## Setup

### Environment Variables

Copy the provided `.env.example` file to a new file named `.env`:

```bash
cp .env.example .env
```

Update `.env` with your actual credentials:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Notion
NOTION_TOKEN=your_notion_integration_token_here
NOTION_DATABASE_ID=your_notion_database_id_here

# Access Control (Comma-separated Telegram usernames without '@')
ALLOWED_USERNAMES=username1,username2,username3
```

### Running Locally (with `uv`)

1. Install dependencies and start the bot:

```bash
uv run -m meal_bot.main
```

### Running with Docker

You can run the bot using Docker Compose, which builds a secure, slim, and read-only container perfectly suited for deployment.

1. Build and start the container in the background:

```bash
docker compose up -d --build
```

2. View the logs to ensure it started correctly:

```bash
docker compose logs -f
```

## Usage

1. Open up the chat with your bot on Telegram.
2. Record and send a **Video Note** directly displaying or describing your meal.
3. The bot will download the video, pass it through the AI nutrition analyst, and respond with a detailed macro and calorie breakdown.
4. The entry is recorded automatically in your connected Notion database!

## License
MIT
