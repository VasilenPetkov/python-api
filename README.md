# Uptime Monitor API

Учебен Python проект за наблюдение на уеб услуги, който постепенно ще
развиваме с DevOps инструменти. Първата версия използва **FastAPI** и **SQLite**.
Не са необходими PostgreSQL, Docker или външни credentials.

## Стартиране

Изпълни от директорията на проекта с Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Интерактивната документация е на `/docs`, OpenAPI описанието — на `/openapi.json`.
Базата се създава автоматично в `data/uptime.sqlite3` и пази данните при рестарт.
По желание `DATABASE_PATH` задава друг път до SQLite файла.

## Първи пример

В друг терминал добави услуга:

```bash
curl -X POST http://127.0.0.1:8000/monitors \
  -H 'Content-Type: application/json' \
  -d '{"name":"Local API","url":"http://127.0.0.1:8000/health","expected_status":200}'
```

Използвай върнатото `id` вместо `1`, ако вече имаш записи:

```bash
curl -X POST http://127.0.0.1:8000/monitors/1/checks
curl http://127.0.0.1:8000/monitors/1/checks
```

Проверката записва HTTP статуса, времето до получаване на response headers,
дали статусът е очакваният и евентуална грешка при свързване.
Не следва redirects и не изтегля response body. Има timeout от 5 секунди
за мрежовите операции. Проверките засега се стартират ръчно през API.

## Endpoints

| Метод | Път | Действие |
|---|---|---|
| GET | `/health` | Проверка на приложението и достъпа до базата |
| POST | `/monitors` | Добавяне на услуга |
| GET | `/monitors` | Списък с услуги |
| GET | `/monitors/{id}` | Една услуга |
| POST | `/monitors/{id}/checks` | Нова HTTP проверка |
| GET | `/monitors/{id}/checks` | История, най-новите първо; `limit` от 1 до 500 |

## Тестове

```bash
python -m pytest -q
```

Тестовете използват временни бази и симулирани HTTP отговори, без външен интернет.
Покриват валидацията, липсващи услуги, успешни и неуспешни проверки,
историята и запазването на данните при рестарт.

## Как да разбереш кода

1. `app/main.py`: входните модели описват JSON данните; декораторите `@app.get`
   и `@app.post` свързват URL адрес с Python функция.
2. `app/database.py`: създава таблиците и отваря връзки към SQLite.
3. `tests/test_api.py`: показва как извикваме API и проверяваме поведението му.

Миграция е версия на промяна в структурата на базата, например добавяне на
колона `interval_seconds`. `CREATE TABLE IF NOT EXISTS` създава първите таблици,
но не обновява съществуващи таблици. Ще добавим миграции преди първата такава
промяна, когато вече имаме данни, които искаме да запазим.

## Следващи стъпки

- Обобщение на резултатите и редакция/изтриване на услуги.
- PostgreSQL, SQLAlchemy и Alembic миграции.
- Фонов worker за периодични проверки.
- Docker Compose и GitHub Actions.
- Deployment, метрики с Prometheus/Grafana и Terraform.

Текущата версия е за локално обучение. Преди публичен deployment ще добавим
автентикация и ограничения за адресите, които API може да проверява.
