SHELL := /bin/sh

# App image name
IMAGE_APP := ai-call-app
DOMAIN := ai-call.24ai-spbconsult.ru
EMAIL := admin@24ai-spbconsult.ru

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
