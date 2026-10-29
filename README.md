See English version below.

## BooktowerBot

Телеграм бот для книжной ярмарки Пражская Книжная Башня. Бот предоставляет гостям ярмарки нужную информацию о событиях, расписании, участниках и других аспектах ярмарки.

## Архитектура и Структура Проекта

Проект построен по модульному принципу и разделен на следующие компоненты:

- `bot/` — Telegram-бот (навигация, расписание, участники, схема площадки, вишлист, интерактивная CLI-симуляция).
- `admin/` — Веб-консоль администратора (управление расписанием, участниками, картами, отправка рассылок, UX-аналитика, импорт через LLM).
- `assets/` — Постоянное хранилище данных: базы SQLite (`analytics.db`, `wishlist.db`, `.admin_users.db`), JSON-файлы расписаний и участников, схемы площадок.
- `auth_approval/` — Утилита интерактивного подтверждения учетных записей администраторов.
- `main.py` — Основной скрипт для одновременного запуска бота и админ-панели.
- `tests/` — Набор модульных и интеграционных тестов (`pytest`).

## Используемые сервисы

- **Telegram Bot API** — взаимодействие с пользователями через мессенджер Telegram.
- **OpenRouter API** — интеграция с LLM для структурирования и конвертации расписания в формат JSON.
- **Поиск по ISBN и распознавание штрихкодов** — поиск библиографической информации через Open Library (`openl`), Google Books (`goob`), Wikipedia (`wiki`) с помощью библиотеки `isbnlib`, а также сканирование штрихкодов с изображений с помощью `zxing-cpp` и `Pillow`.
- **SQLite** — легковесная база данных для пользователей консоли, аналитики и списков избранного.
- **Docker / Podman / Fly.io** — контейнеризация и облачный деплой.

## Функции и Использование

### Команды Telegram-бота
Бот поддерживает управление через интерактивные кнопки меню и прямые текстовые команды:

- `/start` — Запустить или перезапустить бота.
- `/map` — Показать карту площадки.
- `/timetables` — Расписания (по дням и локациям).
- `/children` — Детская программа.
- `/masterclasses` (или `/mc`) — Расписание и информация о мастер-классах.
- `/recommendations` (или `/recs`) — Подборка рекомендаций книг.
- `/participants` — Список участников ярмарки.
- `/wishlist` — Персональный вишлист гостя (добавить книгу, просмотреть свой список).
- `/help` — Показать справочное сообщение со списком команд и контактами разработчика.

### Возможности панели администратора
- Управление расписанием и списком участников в реальном времени.
- Быстрый импорт расписаний из текста с помощью нейросетей (LLM).
- Загрузка и обновление карт площадки.
- Массовая рассылка сообщений пользователям бота.
- Детальная UX-аналитика активности и популярности разделов.

## Установка и Администрирование

# Установка на хостинг с помощью Docker (без Fly.io)

Пошаговая инструкция по запуску бота на собственном сервере (VPS под управлением Ubuntu/Debian):

### 1. Установка Docker и Git на сервере
Подключитесь к вашему серверу по SSH и выполните команды:
```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2
```

### 2. Клонирование репозитория
```bash
git clone https://github.com/vorobvla/BookTowerBot.git
cd booktower
```

### 3. Получение токена Telegram-бота
1. Откройте Telegram и найдите официального бота [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot` и следуйте подсказкам: укажите имя бота и его username (должен оканчиваться на `bot`).
3. Скопируйте выданный токен API (например, `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### 4. Настройка файла переменных окружения (.env)
Создайте файл `.env` из шаблона:
```bash
cp .env.example .env
```
Откройте файл в текстовом редакторе (`nano .env`) и вставьте полученный токен, а так же добавьте остальные ключи и прочие настройки, описанные .env.example :
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
OPENROUTER_API_KEY=your_openrouter_api_key_if_used
ADMIN_PORT=8080
```
Сохраните изменения (`Ctrl+O`, `Enter`, затем `Ctrl+X`).

### 5. Запуск контейнеров
Запустите бота и веб-консоль в фоновом режиме:
```bash
sudo docker compose up -d --build
```
Для проверки логов выполните:
```bash
sudo docker compose logs -f
```
Для остановки контейнера:
```bash
sudo docker compose down
```

Для подключения к работающему контейнеру и выполнения команд внутри него (например, для одобрения администраторов):
```bash
sudo docker compose exec booktower_app bash
```

---

# Установка на хостинг с помощью Fly.io

Большинство настроек можно выполнить напрямую через веб-панель Fly.io:

### 1. Создание приложения в веб-панели (Dashboard)
Если приложение еще не создано:
1. Перейдите в [Fly.io Dashboard](https://fly.io/dashboard) и нажмите **Create App** (или **Launch an App**).
2. Выберите импорт из Git-репозитория и укажите ссылку на ваш репозиторий проекта.
3. Задайте имя приложения (оно должно совпадать с параметром `app` в `fly.toml` или указываться через флаг `-a`).

### 2. Настройка в веб-панели Fly.io (Dashboard)
1. **Секреты и переменные (Secrets)**:
   В панели управления вашим приложением перейдите в раздел **Secrets** и добавьте значения переменных окружения, указанных в `.env.example`, например:
   - `TELEGRAM_BOT_TOKEN` — токен от @BotFather
   - `OPENROUTER_API_KEY` — ключ API OpenRouter (при использовании LLM)
2. **Постоянный диск (Volumes)**:
   В разделе **Volumes** создайте том с именем `booktower_data` (размером 1 GB), который автоматически смонтируется в папку `/app/assets` для сохранения баз данных и расписаний.

### 3. Деплой
Запустите развертывание проекта:
```bash
fly deploy
```

---

# Адиминистрирование:

### Консоль (веб)
1. Откройте браузер и перейдите по адресу: `http://<IP_вашего_сервера>:8080` (или `http://localhost:8080` при локальном запуске).
2. Зарегистрируйте новую учетную запись администратора через форму регистрации.

### Одобрение администратора (пользователя консоли)
В целях безопасности новые учетные записи не получают доступ автоматически и требуют подтверждения:
```bash
# На хосте / сервере:
./auth_approval/approveAdmins.sh

# Или внутри запущенного Docker-контейнера:
docker compose exec booktower_app ./auth_approval/approveAdmins.sh
```
Скрипт по очереди покажет ожидающие заявки с возможностью одобрить (`y`) или отклонить (`n`) пользователя.

Для очистки всех неподтвержденных заявок:
```bash
./auth_approval/approveAdmins.sh --clear
```

## Тестирование

# Юнит-тесты
Запуск полного набора автоматических тестов с помощью `pytest`:
```bash
pytest -v
```

# Локальный запуск

### 1. Установка зависимостей в виртуальное окружение
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Запуск в режиме симуляции (без токена Telegram и интернета)
Позволяет интерактивно протестировать все команды и кнопки бота прямо в терминале:
```bash
python main.py --local
```

### 3. Локальный запуск бота и веб-консоли
```bash
python main.py
```
*(Требуется указать `TELEGRAM_BOT_TOKEN` и все остальные параметры в `.env`, их стурктура и описание есть в env.example)*

## Советы для разработчиков

1. **Безопасность пользовательских данных**:
   Никогда не храните конфиденциальные данные пользователей (включая `chat_id`, `user_id` и любые идентификаторы) в открытом виде в базах данных или логах — обязательно используйте хеширование с добавлением соли.

2. **Изоляция тестового окружения**:
   Для тестирования всегда создавайте отдельного бота с отдельным токеном через @BotFather. Никогда не проводите тестирование на рабочей версии бота.

3. **Известные проблемы и планы по развитию (Known Issues)**:
   - **Особенности Markdown**: Спецсимволы (например, `_`, `*`) экранируются, однако в сложных текстах могут вызывать сбои форматирования Telegram; рекомендуется рассмотреть перевод форматирования сообщений на HTML (`parse_mode="HTML"`).
   - **Поиск по ISBN**: Алгоритм поиска требует улучшений, а также исправления ошибок в транслитерации названий.
   - **Запланированные функции**: Возможность быстрого добавления книги в вишлист прямо из раздела рекомендаций, а также сохранение интересных событий в избранное с добавлением в календарь.

---

# English Version

## BooktowerBot

Telegram bot for the Prague Book Tower book fair. The bot provides visitors with all necessary information about events, schedules, participants, and other aspects of the fair.

## Architecture & Project Structure

The project is built on a modular OOP principle and divided into the following components:

- `bot/` — Telegram bot (navigation, schedule, participants, venue map, wishlist, interactive CLI simulation).
- `admin/` — Web admin console (schedule management, participants, maps, broadcast messaging, UX analytics, LLM import).
- `assets/` — Persistent data storage: SQLite databases (`analytics.db`, `wishlist.db`, `.admin_users.db`), JSON schedule/participant files, venue maps.
- `auth_approval/` — Utility for interactive administrator account approval.
- `main.py` — Main entry point to run both the bot and admin panel concurrently.
- `tests/` — Suite of unit and integration tests (`pytest`).

## Services Used

- **Telegram Bot API** — user interaction via Telegram messenger.
- **OpenRouter API** — LLM integration for structuring and converting schedules into JSON format.
- **ISBN Search & Barcode Recognition** — bibliographic metadata lookup via Open Library (`openl`), Google Books (`goob`), and Wikipedia (`wiki`) using `isbnlib`, as well as barcode scanning from images using `zxing-cpp` and `Pillow`.
- **SQLite** — lightweight database for admin users, analytics, and wishlists.
- **Docker / Podman / Fly.io** — containerization and cloud deployment.

## Features & Usage

### Telegram Bot Commands
The bot supports navigation via interactive keyboard buttons and direct text commands:

- `/start` — Start or restart the bot.
- `/map` — Show venue map.
- `/timetables` — Event schedules (by day and location).
- `/children` — Children's program.
- `/masterclasses` (or `/mc`) — Schedule and details of masterclasses.
- `/recommendations` (or `/recs`) — Curated book recommendations.
- `/participants` — List of book fair participants.
- `/wishlist` — Personal visitor wishlist (add book, view list).
- `/help` — Display help message with command list and developer contacts.

### Admin Console Features
- Real-time schedule and participant list management.
- Quick schedule import from text using neural networks (LLM).
- Uploading and updating venue maps.
- Broadcast messaging to bot users.
- Detailed UX analytics on user activity and section popularity.

## Installation & Administration

# Hosting Setup with Docker (without Fly.io)

Step-by-step guide to running the bot on your own server (Ubuntu/Debian VPS):

### 1. Installing Docker and Git on the Server
Connect to your server via SSH and run:
```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2
```

### 2. Cloning the Repository
```bash
git clone https://github.com/vorobvla/BookTowerBot.git
cd booktower
```

### 3. Getting a Telegram Bot Token
1. Open Telegram and find [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow prompts: specify bot name and username (must end with `bot`).
3. Copy the issued API token (e.g., `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### 4. Configuring Environment Variables (.env)
Create a `.env` file from the template:
```bash
cp .env.example .env
```
Open the file in a text editor (`nano .env`), paste your token, and configure any additional settings described in `.env.example`:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
OPENROUTER_API_KEY=your_openrouter_api_key_if_used
ADMIN_PORT=8080
```
Save changes (`Ctrl+O`, `Enter`, then `Ctrl+X`).

### 5. Running Containers
Start the bot and web console in background mode:
```bash
sudo docker compose up -d --build
```
To check logs:
```bash
sudo docker compose logs -f
```
To stop the container:
```bash
sudo docker compose down
```

To connect to the running container and execute commands inside it (e.g., for approving admins):
```bash
sudo docker compose exec booktower_app bash
```

---

# Hosting Setup with Fly.io

Most settings can be configured directly via the Fly.io web console (Dashboard):

### 1. Creating the App in the Web Dashboard
If the app is not created yet:
1. Go to [Fly.io Dashboard](https://fly.io/dashboard) and click **Create App** (or **Launch an App**).
2. Choose to import from a Git repository and provide your repository URL.
3. Set the application name (it should match the `app` value in `fly.toml` or be specified with `-a`).

### 2. Configuration in the Fly.io Dashboard
1. **Secrets & Environment Variables**:
   In your app settings on Fly.io, go to **Secrets** and add the variables from `.env.example`, for example:
   - `TELEGRAM_BOT_TOKEN` — token from @BotFather
   - `OPENROUTER_API_KEY` — OpenRouter API key (if using LLM)
2. **Persistent Storage (Volumes)**:
   In the **Volumes** section, create a volume named `booktower_data` (1 GB size), which will automatically mount to `/app/assets` to persist databases and schedules.

### 3. Deployment
Deploy the application:
```bash
fly deploy
```

---

# Administration:

### Web Console
1. Open your browser and navigate to `http://<YOUR_SERVER_IP>:8080` (or `http://localhost:8080` for local runs).
2. Register a new administrator account using the registration form.

### Approving an Administrator (Console User)
For security reasons, newly registered accounts are not active by default and require manual approval:
```bash
# On the host / server:
./auth_approval/approveAdmins.sh

# Or inside the running Docker container:
docker compose exec booktower_app ./auth_approval/approveAdmins.sh
```
The script will prompt you for each pending user to approve (`y`) or reject (`n`).

To clear all pending approval requests:
```bash
./auth_approval/approveAdmins.sh --clear
```

## Testing

# Unit Tests
Run the automated test suite using `pytest`:
```bash
pytest -v
```

# Local Execution

### 1. Installing Dependencies in a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Simulation Mode (No Telegram Token or Internet Required)
Allows interactive testing of all bot commands and buttons directly in the terminal:
```bash
python main.py --local
```

### 3. Local Execution of Bot and Web Console
```bash
python main.py
```
*(Requires setting `TELEGRAM_BOT_TOKEN` and other parameters in `.env`, structured as shown in `env.example`)*

## Developer Advice

1. **User Data Security**:
   Never store sensitive user data (including `chat_id`, `user_id`, or any identifiers) as plain text in databases or logs — always use salted hashing.

2. **Test Environment Isolation**:
   Always create a dedicated test bot with a separate token via @BotFather. Never run tests on the production bot instance.

3. **Known Issues & Development Plans**:
   - **Markdown Quirks**: Special characters (e.g., `_`, `*`) are escaped, but may still cause formatting issues in complex Telegram messages; consider migrating message formatting to HTML (`parse_mode="HTML"`).
   - **ISBN Search**: The search algorithm needs improvement, as well as fixing title transliteration issues.
   - **Planned Features**: Ability to quickly add books to the wishlist directly from recommendations, and bookmarking interesting events with calendar integration.
