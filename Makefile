COMPOSE ?= docker compose

# Состав сервисов по заданиям.
# Синхронизировать с docker-compose.yaml при добавлении сервисов в ходе выполнения тасок.
TASK1_SERVICES := keycloak_db keycloak openldap bionicpro-auth frontend nginx-gateway
TASK2_SERVICES := $(TASK1_SERVICES) crm_db clickhouse airflow-db airflow-webserver airflow-scheduler bionicpro-api
TASK3_SERVICES := $(TASK2_SERVICES) minio nginx
TASK4_SERVICES := $(TASK3_SERVICES) kafka kafka-connect debezium-init

.DEFAULT_GOAL := help

help: ## Список доступных целей
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | grep -vE '^help:' | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

build: ## Собрать образы
	$(COMPOSE) build

up-task1: ## Окружение задания 1: Keycloak, OpenLDAP, bionicpro-auth, frontend
	$(COMPOSE) up -d --build $(TASK1_SERVICES)

up-task2: ## Окружение задания 2: + CRM БД, ClickHouse, Airflow
	$(COMPOSE) up -d --build $(TASK2_SERVICES)

up-task3: ## Окружение задания 3: + MinIO (S3), Nginx (CDN)
	$(COMPOSE) up -d --build $(TASK3_SERVICES)

up-task4: ## Окружение задания 4: + Kafka, Kafka Connect (Debezium)
	$(COMPOSE) up -d --build $(TASK4_SERVICES)

up-all: ## Поднять все сервисы (финальное состояние)
	$(COMPOSE) up -d --build

down: ## Остановить и удалить контейнеры
	$(COMPOSE) down

restart: ## Перезапустить контейнеры
	$(COMPOSE) restart

reset-keycloak: ## Переимпорт realm: очистить БД Keycloak и перезапустить его
	$(COMPOSE) stop keycloak keycloak_db
	rm -rf postgres-keycloak-data
	$(COMPOSE) up -d --no-deps keycloak_db keycloak

ps: ## Статус сервисов
	$(COMPOSE) ps

logs: ## Логи всех сервисов
	$(COMPOSE) logs -f --tail=200

clean: ## Остановить и удалить контейнеры и тома
	$(COMPOSE) down -v --remove-orphans
