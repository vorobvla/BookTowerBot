# BookTowerBot

A simple, modular, and testable Telegram bot built to assist visitors at a Book Fair. It delivers venue maps, schedules/timetables, and curated recommendations through both text commands and interactive buttons.

---

## 🌟 Key Features

1. **Venue Map (`/map` or `🗺 Event Map` button):**
   - ASCII event layout and pavilion breakdown (Fiction, Non-fiction, Comics/Kids, Main Stage, Food Court, Info Desk).
2. **Timetable & Schedule (`/timetable` or `📅 Timetable` button):**
   - Chronological breakdown of opening ceremonies, author meet & greets, panels, and award ceremonies.
3. **Recommendations (`/recommendations`, `/recs`, or `⭐ Recommendations` button):**
   - Curated visitor picks for standout book booths, featured releases, and tips.
4. **Interactive Navigation:**
   - Persistent `ReplyKeyboardMarkup` at the bottom of the chat for one-tap navigation.
   - Dynamic `InlineKeyboardMarkup` buttons on responses.
   - Command support (`/start`, `/map`, `/timetable`, `/recommendations`, `/recs`, `/help`).
5. **Local Testing & Simulation:**
   - Integrated terminal interactive simulation mode (`--local`) for rapid manual testing without requiring Telegram tokens or active internet connections.
   - Comprehensive automated unit test suite with `pytest`.

---

## 📁 Project Structure

```
.
├── Dockerfile           # Production container definition
├── docker-compose.yml   # Multi-container / deployment orchestration
├── .dockerignore        # Docker build context exclusions
├── .env.example         # Template for environment variables
├── .gitignore           # Git ignore rules
├── main.py              # Application entry point (live polling & local CLI simulation)
├── requirements.txt     # Python dependencies
├── bot/
│   ├── __init__.py
│   ├── app.py           # Application builder & handler registration
│   ├── config.py        # Environment configuration
│   ├── content.py       # Message templates and placeholder data
│   ├── handlers.py      # Async handlers for commands, messages, and inline buttons
│   └── keyboards.py     # Reply and Inline keyboard builders
└── tests/
    ├── __init__.py
    ├── test_app.py        # Application setup and handler registration tests
    ├── test_content.py    # Message content validation tests
    ├── test_handlers.py   # Asynchronous handler and interaction tests
    └── test_keyboards.py  # Keyboard layout tests
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Local Interactive Simulation (No Token Needed)

Test all bot commands and button interactions in the terminal without configuring Telegram credentials:

```bash
python main.py --local
```

### 3. Run Automated Unit Tests

Execute the complete test suite:

```bash
pytest -v
```

### 4. Run Live Telegram Bot

Set your BotFather token and start polling:

```bash
# Using environment variable
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
python main.py

# Or via command-line argument
python main.py --token "your_telegram_bot_token_here"
```

---

##  Running with Docker

### Using Docker Compose (Recommended)

1. Create your `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set your `TELEGRAM_BOT_TOKEN`:
   ```env
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
3. Build and start the bot container in background:
   ```bash
   docker compose up -d --build
   ```
4. View logs:
   ```bash
   docker compose logs -f
   ```
5. Stop the bot:
   ```bash
   docker compose down
   ```

### Using Plain Docker

```bash
# Build the image
docker build -t booktowerbot .

# Run container with environment variable
docker run -d --name booktower_bot --restart unless-stopped -e TELEGRAM_BOT_TOKEN="your_token_here" booktowerbot

# Check logs
docker logs -f booktower_bot
```

---

## 🤖 Available Commands & Interactions

| Action | Command | Reply Keyboard Button | Inline Callback |
|---|---|---|---|
| **Welcome Menu** | `/start` | — | — |
| **Event Map** | `/map` | `🗺 Event Map` | `action_map` |
| **Timetable** | `/timetable` | `📅 Timetable` | `action_timetable` |
| **Recommendations** | `/recommendations`, `/recs` | `⭐ Recommendations` | `action_recommendations` |
| **Help & Guide** | `/help` | `ℹ️ Help` | `action_help` |

---

## 🌐 Deploying to Hosting / Server

To keep the bot running 24/7 on your server/VPS (e.g., Ubuntu, Debian):

1. **Clone your repository on the server:**
   ```bash
   git clone https://github.com/<your-username>/<your-repo-name>.git
   cd <your-repo-name>
   ```
2. **Create and configure `.env`:**
   ```bash
   cp .env.example .env
   nano .env # Paste your TELEGRAM_BOT_TOKEN
   ```
3. **Start the container:**
   ```bash
   docker compose up -d --build
   ```
The bot will run continuously in the background and automatically restart if the server reboots.


# AssetStructure
The Assests must be structured as follows:

```bash
$ASSETS_FILE/
├── maps/
├── timetables/
├── recommendations/
```
the root_dir path is pecified in the env