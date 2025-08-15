# Ai-Call

## Docker deploy (Nginx + Node)

Domain: `ai-call.24ai-spbconsult.ru`

### Local build and run
```bash
docker compose build
docker compose up -d
```

App is served via Nginx on port 80. Nginx proxies `/ws` and `/health` to the app and serves static files from `public/`.

### TLS (production)
On the server (with DNS A record pointing to this host):
```bash
sudo apt-get update && sudo apt-get install -y certbot
docker run --rm -it \
  -v certbot-etc:/etc/letsencrypt \
  -v certbot-var:/var/lib/letsencrypt \
  certbot/certbot certonly --standalone \
  -d ai-call.24ai-spbconsult.ru --agree-tos -m admin@24ai-spbconsult.ru --non-interactive
```

Then replace `nginx/nginx.conf` with a TLS-enabled server block or add a new file under `/etc/nginx/conf.d/` mounting certs volumes into the nginx container.

---

## Telegram Bot + PostgreSQL

A Telegram bot (aiogram v3) and a PostgreSQL database were added to support:
- user registration (`/start`) — stores Telegram ID and username
- inline menu: «Начать звонок», «Добавить контакт»
- call submenu: «Создать ссылку», «Выбрать из контактов», «Назад»
- invite link to add contacts: users who open the link are added to inviter’s contacts
- creating unique room links and notifying both participants in Telegram

### Services
- `db`: PostgreSQL 16
- `bot`: aiogram bot (Python 3.11)

Tables are created automatically on bot start.

### Env vars
- `BOT_TOKEN`: Telegram bot token from BotFather
- `APP_PUBLIC_BASE_URL`: Public base URL of the web app (e.g. `http://localhost:8080` in dev or `https://ai-call.24ai-spbconsult.ru` in prod)

Create a `.env` file in the project root:
```env
BOT_TOKEN=xxxxxxxx:yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
APP_PUBLIC_BASE_URL=http://localhost:8080
```

### Local dev quickstart
```bash
docker compose -f docker-compose.dev.yml up -d --build
```
Open `http://localhost:8080` to access the web client.

In Telegram, open your bot and press Start. You will be prompted to enter a username. After registration use the inline menu.

### How links work
- «Создать ссылку» — generates a random unique room ID and returns `APP_PUBLIC_BASE_URL/call.html?room=<id>`
- «Выбрать из контактов» — search your saved contacts, then a room is created and the link is sent to both you and the contact

The web client (`public/call.html`) auto-fills the Room ID from `?room=` if present.
