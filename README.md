# Платёж прошёл? Докажи

Сервис проведения платёжных операций через внешний `provider-simulator`. Сервис сохраняет состояние операций, устойчив к повторным и конкурентным запросам и продолжает обработку незавершённых операций после перезапуска.

## Технологии

- Python 3.14;
- FastAPI;
- PostgreSQL 17;
- SQLAlchemy и Alembic;
- HTTPX;
- Docker Compose;
- pytest.

## Запуск

Для запуска приложения достаточно Docker и Docker Compose. Локальный Python 3.14 требуется только для запуска тестов.

```bash
docker compose up --build
```

Команда:

1. запускает PostgreSQL;
2. выполняет миграции Alembic;
3. запускает сервис на порту `8080`;
4. запускает симулятор провайдера на порту `8081`.

Команда запускается в режиме отображения логов и занимает текущий терминал. Последующие команды выполняйте в отдельном терминале.

Проверка готовности:

```bash
curl --include http://localhost:8080/health
```

Ожидаемый статус:

```text
HTTP/1.1 200 OK
```

Интерактивная документация API доступна по адресу:

```text
http://localhost:8080/docs
```

## API

| Метод | Маршрут | Назначение |
|---|---|---|
| `GET` | `/health` | Проверить готовность сервиса |
| `POST` | `/operations` | Создать операцию |
| `POST` | `/operations/{id}/submit` | Запланировать отправку |
| `GET` | `/operations/{id}` | Получить текущее состояние |
| `GET` | `/operations/{id}/events` | Получить историю событий |
| `POST` | `/receipts` | Принять callback-квитанцию провайдера |

## Сквозной сценарий

Команды ниже рассчитаны на Bash, Git Bash или WSL.

Создадим уникальный идентификатор операции:

```bash
OPERATION_ID="readme-$(date +%s)"
```

### 1. Создание операции

```bash
curl --include \
  --request POST \
  "http://localhost:8080/operations" \
  --header "Content-Type: application/json" \
  --data "{\"operationId\":\"${OPERATION_ID}\",\"amount\":\"1000.00\",\"currency\":\"RUB\",\"description\":\"README check\"}"
```

Ожидается статус `201 Created` и состояние:

```json
{
  "status": "CREATED",
  "providerPaymentId": null
}
```

### 2. Отправка операции

```bash
curl --include \
  --request POST \
  "http://localhost:8080/operations/${OPERATION_ID}/submit"
```

Первый запрос возвращает `202 Accepted` и переводит операцию в `PROCESSING`.

Повторный запрос не создаёт новый платёж и возвращает текущее состояние с `200 OK`:

```bash
curl --include \
  --request POST \
  "http://localhost:8080/operations/${OPERATION_ID}/submit"
```

### 3. Проверка состояния

Подождите несколько секунд, чтобы симулятор отправил callback:

```bash
sleep 2
```

Получите текущее состояние:

```bash
curl --include \
  "http://localhost:8080/operations/${OPERATION_ID}"
```

Операция сначала может находиться в `PROCESSING`, а после callback получает финальное состояние `COMPLETED` или `REJECTED`.

### 4. Проверка истории

```bash
curl --include \
  "http://localhost:8080/operations/${OPERATION_ID}/events"
```

События возвращаются в порядке их фиксации. Обычная последовательность:

```text
CREATED → PROCESSING → COMPLETED/REJECTED
```

## Проверка восстановления после перезапуска

Создайте ещё одну операцию:

```bash
RECOVERY_ID="recovery-$(date +%s)"

curl --include \
  --request POST \
  "http://localhost:8080/operations" \
  --header "Content-Type: application/json" \
  --data "{\"operationId\":\"${RECOVERY_ID}\",\"amount\":\"500.00\",\"currency\":\"RUB\",\"description\":\"Recovery check\"}"
```

Запросите отправку:

```bash
curl --include \
  --request POST \
  "http://localhost:8080/operations/${RECOVERY_ID}/submit"
```

Сразу остановите и снова запустите сервис кандидата:

```bash
docker compose stop candidate-service
docker compose start candidate-service
docker compose up --wait
```

Проверьте операцию:

```bash
curl --include \
  "http://localhost:8080/operations/${RECOVERY_ID}"
```

Операция и её история сохраняются в PostgreSQL. Если операция осталась в `PROCESSING`, worker автоматически продолжит её отправку с прежним `Idempotency-Key`, равным `operationId`.

При восстановлении не используется `docker compose down -v`, поскольку флаг `-v` удаляет volume PostgreSQL вместе с данными.

## Тесты

Убедитесь, что сервисы запущены:

```bash
docker compose up --build --wait
```

Установите зависимости для тестирования:

```bash
python -m pip install -r requirements-dev.txt
```

Запустите тесты:

```bash
python -m pytest
```

Тесты проверяют конкурентные запросы `submit` и конкурентную обработку одинаковых callback-квитанций.

## Хранение данных

Данные PostgreSQL хранятся в именованном Docker volume `postgres-data`.

Обычная остановка удаляет контейнеры, но сохраняет данные:

```bash
docker compose down
```

Повторный запуск восстановит контейнеры с сохранёнными данными:

```bash
docker compose up --build
```

Остановка с удалением volume полностью удаляет локальные операции и события:

```bash
docker compose down -v
```

## Основные гарантии

- намерение отправки сохраняется до обращения к провайдеру;
- только первый `submit` переводит операцию из `CREATED` в `PROCESSING`;
- `Idempotency-Key` и `X-Correlation-ID` равны `operationId`;
- сетевые ошибки и `503` повторяются с тем же ключом;
- финальный статус устанавливается только callback-квитанцией;
- повторная квитанция не создаёт повторный переход;
- незавершённые операции автоматически восстанавливаются после перезапуска.