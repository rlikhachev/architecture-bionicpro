# BionicPRO — Architecture
Учебный архитектурный проект по кейсу BionicPRO (производитель бионических протезов)

## Оглавление
- [Задание 1. Повышение безопасности системы](#задание-1-повышение-безопасности-системы)
- [Задание 2. Разработка сервиса отчётов](#задание-2-разработка-сервиса-отчётов)
- [Задание 3. Снижение нагрузки на базу данных](#задание-3-снижение-нагрузки-на-базу-данных)
- [Задание 4. Повышение оперативности и стабильности работы CRM](#задание-4-повышение-оперативности-и-стабильности-работы-crm)
- [Инфраструктура и общие файлы](#инфраструктура-и-общие-файлы)
- [Запуск](#запуск)
- [Пользователи](#пользователи)
- [Админ-панели](#админ-панели)

## Задание 1. Повышение безопасности системы
PKCE-флоу, бэкенд-сервис сессий, фронтенд без токенов, LDAP-федерация, MFA, Яндекс ID.

- Диаграмма: [docs/security-architecture.drawio](docs/security-architecture.drawio)
- Бэкенд-сервис аутентификации: [bionicpro-auth/](bionicpro-auth/)
- Фронтенд на сессиях (без прямой интеграции с Keycloak): [frontend/](frontend/)
  - [frontend/src/App.tsx](frontend/src/App.tsx)
- Keycloak realm:
  - [keycloak/realm-export.json](keycloak/realm-export.json) — исходный realm (импортируется при старте)
  - [keycloak/keycloak-results-export.json](keycloak/keycloak-results-export.json) — результат после всех настроек
- LDAP: [ldap/config.ldif](ldap/config.ldif)

## Задание 2. Разработка сервиса отчётов
Airflow ETL из CRM в витрину ClickHouse, API `/reports`, читающий готовую витрину.

- Диаграмма: [docs/reports-architecture.drawio](docs/reports-architecture.drawio)
- Airflow (отдельная папка): [airflow/](airflow/)
- API (фактическое чтение из ClickHouse): [api/](api/)
- Витрина ClickHouse: [clickhouse/init/01_reports_dm.sql](clickhouse/init/01_reports_dm.sql)
- CRM (сид-данные: клиенты, протезы, телеметрия): [crm/init.sql](crm/init.sql)

## Задание 3. Снижение нагрузки на базу данных
Кеш отчётов в S3 (MinIO) и раздача через CDN (Nginx).
- Nginx (отдельная папка): [nginx/](nginx/)
- Развёртывание MinIO и Nginx: [docker-compose.yaml](docker-compose.yaml) (сервисы `minio`, `minio-init`, `nginx`, `nginx-gateway`)

## Задание 4. Повышение оперативности и стабильности работы CRM
CDC из CRM через Debezium → Kafka → ClickHouse.

- Debezium-коннектор (отдельная папка): [debezium/](debezium/)
- Приём данных в ClickHouse [clickhouse/init/02_cdc.sql](clickhouse/init/02_cdc.sql)
- Развёртывание Kafka и kafka-connect: [docker-compose.yaml](docker-compose.yaml) (сервисы `kafka`, `kafka-connect`, `debezium-init`)

## Инфраструктура и общие файлы
- [docker-compose.yaml](docker-compose.yaml) — все сервисы стека
- [Makefile](Makefile) — запуск окружений по заданиям и вспомогательные цели

## Запуск
Окружение поднимается через `Makefile` (накопительный состав сервисов):

```bash
make up-task1   # Keycloak, OpenLDAP, bionicpro-auth, frontend, nginx-gateway
make up-task2   # + CRM БД, ClickHouse, Airflow, bionicpro-api
make up-task3   # + MinIO (S3), Nginx (CDN)
make up-task4   # + Kafka, Kafka Connect (Debezium) — полный стек
make up-all     # все сервисы (финальное состояние)

make ps         # статус
make logs       # логи
make down       # остановить
make clean      # остановить и удалить контейнеры и тома
make reset-keycloak  # переимпорт realm (очистка БД Keycloak)
```

## Точки входа:
- Gateway (frontend + auth + reports): http://localhost:8085
- Keycloak: http://localhost:8080 (admin/admin, realm `reports-realm`)
- Airflow: http://localhost:8082
- MinIO console: http://localhost:9001

## Пользователи

### Приложение (realm `reports-realm`)
Вход через gateway http://localhost:8085. Для всех пользователей realm при первом входе
Keycloak требует зарегистрировать OTP (MFA, required action `CONFIGURE_TOTP`).

| Логин | Пароль | Роль | Отчёты |
|---|---|---|---|
| `prothetic1` | `prothetic123` | `prothetic_user` | есть |
| `prothetic2` | `prothetic123` | `prothetic_user` | есть |
| `prothetic3` | `prothetic123` | `prothetic_user` | есть |
| `user1` | `password123` | `user` | нет |
| `user2` | `password123` | `user` | нет |
| `admin1` | `admin123` | `administrator` | нет |

Отчёты есть только у `prothetic1/2/3`: их `sub` совпадает с `keycloak_user_id` в CRM,
поэтому данные попадают в витрину `reports_dm.mart_crm_reports`.

### LDAP (OpenLDAP, федерация в Keycloak)

| Логин (uid) | Пароль | Группа |
|---|---|---|
| `john.doe` | `password` | `prothetic_user` |
| `jane.smith` | `password` | `user` |
| `alex.johnson` | `password` | `prothetic_user` |

## Админ-панели
| Сервис | URL | Логин | Пароль |
|---|---|---|---|
| Keycloak (master realm) | http://localhost:8080 | `admin` | `admin` |
| Airflow | http://localhost:8082 | `admin` | `admin` |
| MinIO console | http://localhost:9001 | `bionicpro` | `bionicpro-secret` |

