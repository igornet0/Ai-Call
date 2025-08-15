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
