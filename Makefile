SHELL := /bin/sh

# App image name
IMAGE_APP := ai-call-app
DOMAIN := ai-call.24ai-spbconsult.ru
EMAIL := admin@24ai-spbconsult.ru
TURN_USER := aiuser
TURN_PASS := supersecretpassword
# Set this when running host-turn-setup: make host-turn-setup PUBLIC_IP=1.2.3.4
PUBLIC_IP :=

# ------- Dev targets -------
.PHONY: dev-build dev-up dev-down dev-logs

dev-build:
	docker compose -f docker-compose.dev.yml build

dev-up:
	docker compose -f docker-compose.dev.yml up -d

dev-down:
	docker compose -f docker-compose.dev.yml down
dev-logs:
	docker compose -f docker-compose.dev.yml logs -f

# ------- Local project targets -------
.PHONY: install build start

install:
	npm ci

build:
	npm run build

start:
	node dist/index.js

# ------- Dev per-module targets -------
.PHONY: dev-up-% dev-down-% dev-logs-% dev-build-%

dev-up-%:
	docker compose -f docker-compose.dev.yml up -d $*

dev-down-%:
	-docker compose -f docker-compose.dev.yml stop $*
	-docker compose -f docker-compose.dev.yml rm -f $*

dev-logs-%:
	docker compose -f docker-compose.dev.yml logs -f $*

dev-build-%:
	docker compose -f docker-compose.dev.yml build $*

# ------- Prod targets -------
.PHONY: prod-build prod-up prod-down prod-logs

prod-build:
	docker compose -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

# ------- Prod per-module targets -------
.PHONY: prod-up-% prod-down-% prod-logs-% prod-build-%

prod-up-%:
	docker compose -f docker-compose.prod.yml up -d $*

prod-down-%:
	-docker compose -f docker-compose.prod.yml stop $*
	-docker compose -f docker-compose.prod.yml rm -f $*

prod-logs-%:
	docker compose -f docker-compose.prod.yml logs -f $*

prod-build-%:
	docker compose -f docker-compose.prod.yml build $*

# ------- TLS with certbot (HTTP-01 webroot) -------
.PHONY: cert-issue cert-renew cert-dryrun

cert-issue:
	docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d $(DOMAIN) --email $(EMAIL) --agree-tos --non-interactive
	docker compose -f docker-compose.prod.yml exec nginx nginx -s reload || true

cert-renew:
	docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot --quiet
	docker compose -f docker-compose.prod.yml exec nginx nginx -s reload || true

cert-dryrun:
	docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run

# Build only application image (without compose)
.PHONY: image-build
image-build:
	docker build -t $(IMAGE_APP):latest -f Dockerfile .

# ------- Host (pm2 + nginx + certbot + coturn) -------
.PHONY: host-install-deps host-prepare host-deploy-static host-nginx-install host-nginx-reload host-cert-issue host-pm2-up host-pm2-down host-turn-setup host-all

# Install required packages on Ubuntu host (nginx, certbot, node/npm if needed)
host-install-deps:
	sudo apt-get update
	sudo apt-get install -y nginx certbot || true
	command -v node >/dev/null 2>&1 || curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
	command -v node >/dev/null 2>&1 || sudo apt-get install -y nodejs

# Install deps, build app, prepare webroot dirs, deploy static
host-prepare:
	sudo mkdir -p /var/www/ai-call/public /var/www/certbot
	rsync -a --delete public/ /var/www/ai-call/public/
	npm ci
	npm run build

# Re-deploy only static files
host-deploy-static:
	rsync -a --delete public/ /var/www/ai-call/public/

# Install host nginx site config and enable it
host-nginx-install:
	@echo "Installing nginx site for $(DOMAIN)"
	sudo tee /etc/nginx/sites-available/ai-call >/dev/null <<'NGINX'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;

    ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    root /var/www/ai-call/public;
    index index.html;

    # Cache static assets
    location ~* \.(?:js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {
        access_log off;
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri $uri/ /index.html;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # WebSocket signaling
    location /ws {
        proxy_pass http://127.0.0.1:3000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # Health
    location /health {
        proxy_pass http://127.0.0.1:3000/health;
    }

    # ACME over HTTPS (optional)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}
NGINX
	sudo sed -i "s/DOMAIN_PLACEHOLDER/$(DOMAIN)/g" /etc/nginx/sites-available/ai-call
	sudo ln -sf /etc/nginx/sites-available/ai-call /etc/nginx/sites-enabled/ai-call
	$(MAKE) host-nginx-reload

host-nginx-reload:
	@sudo nginx -t && (sudo systemctl reload nginx || sudo nginx -s reload)

# Issue Let's Encrypt certificate using webroot
host-cert-issue:
	sudo certbot certonly --webroot -w /var/www/certbot -d $(DOMAIN) -m $(EMAIL) --agree-tos --no-eff-email --non-interactive
	$(MAKE) host-nginx-reload

# Start/enable app via PM2
host-pm2-up:
	command -v pm2 >/dev/null 2>&1 || sudo npm i -g pm2
	HOST=127.0.0.1 PORT=3000 NODE_ENV=production pm2 start dist/index.js --name ai-call --update-env
	pm2 save
	pm2 startup || true

host-pm2-down:
	-pm2 delete ai-call

# Setup and enable coturn TURN server
host-turn-setup:
	@[ -n "$(PUBLIC_IP)" ] || (echo "ERROR: Set PUBLIC_IP=your_public_ip: make host-turn-setup PUBLIC_IP=1.2.3.4" && exit 1)
	sudo apt-get update && sudo apt-get install -y coturn || true
	sudo tee /etc/turnserver.conf >/dev/null <<TURN
listening-port=3478
fingerprint
lt-cred-mech
realm=$(DOMAIN)
user=$(TURN_USER):$(TURN_PASS)
external-ip=$(PUBLIC_IP)
no-loopback-peers
no-multicast-peers
TURN
	@sudo bash -lc 'if [ -f /etc/default/coturn ]; then sed -i "s/^#\?TURNSERVER_ENABLED=.*/TURNSERVER_ENABLED=1/" /etc/default/coturn || true; else echo "TURNSERVER_ENABLED=1" | tee /etc/default/coturn; fi'
	sudo systemctl enable coturn
	sudo systemctl restart coturn
	sleep 1 && (ss -lntpu | grep 3478 || true)

# One-shot full provisioning on a fresh Ubuntu host
host-all:
	$(MAKE) host-install-deps || true
	$(MAKE) host-prepare
	$(MAKE) host-nginx-install
	$(MAKE) host-cert-issue
	$(MAKE) host-pm2-up
