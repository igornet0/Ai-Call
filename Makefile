SHELL := /bin/sh

# App image name
IMAGE_APP := ai-call-app

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

# Build only application image (without compose)
.PHONY: image-build
image-build:
	docker build -t $(IMAGE_APP):latest -f Dockerfile .
