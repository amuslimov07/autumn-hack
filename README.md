# Прогноз денежных потоков для малого бизнеса

Полноценное локальное веб-приложение для анализа выписок компаний, классификации операций, поиска регулярных платежей, управления будущими событиями, построения прогноза и оценки риска кассового разрыва. Расчёты выполняются backend-сервисом; браузер получает только данные выбранной компании и постраничные результаты.

## Состояние датасета

Целевой кейс содержит синтетические выписки 150 компаний за период 01.10.2024–30.09.2026. Локальный датасет в `data/dataset/` проверен: 150 компаний и 222 420 операций. Датасет исключён из Git. Backend не подменяет его демоданными; актуальное состояние проверяйте через `GET /api/health`.

После распаковки поместите исходные файлы в `data/dataset/`:

```text
data/dataset/
├── companies.csv
├── all_operations.csv
└── statements/
    ├── C001.csv
    └── ...
```

Допустим один источник операций: если есть `all_operations.csv`, он имеет приоритет; иначе используются отдельные CSV из `statements/`. Файлы операций из обоих источников не склеиваются. Формат — UTF-8 с BOM, разделитель `;`, дата `YYYY-MM-DD`, десятичная точка. ИНН читаются строками, ведущие нули сохраняются. Архив не коммитится.

## Архитектура и возможности

- `backend/` — FastAPI, Python-бизнес-логика, загрузка датасета один раз при старте сервиса, SQLite-хранилище корректировок пользователя.
- `frontend/` — React + TypeScript + Vite, Tailwind, React Router, TanStack Query, Recharts, React Hook Form/Zod и Lucide.
- `src/` и `config/` — Python-бизнес-логика прогнозирования и анализа, используемая backend.
- `data/demo/` — синтетические CSV для тестов Python-модулей; они не подключаются как источник веб-приложения.

Веб-приложение содержит обзор выбранной компании, прогноз/риски, серверно-фильтруемую и постраничную историю, категории, регулярные серии, календарь будущих событий, качество моделей и список компаний. Выбор компании обновляет все React Query ключи, а SQLite-записи ограничены `company_id`. Остатки разных компаний не суммируются.

Операции нормализуются как `+amount` для поступления и `-amount` для списания. Остаток на конец дня берётся один раз на дату, а начальный остаток рассчитывается как `balance_eod - сумма знаковых операций`. Соседние даты проверяются на согласованность. Дни без строк не добавляются в фактическую историю; при ежедневном прогнозировании используются непрерывные ряды, и отсутствие наблюдений отмечается как ограничение/неопределённость, а не объявляется подтверждённым нулевым потоком.

Автоматическая категоризация — объяснимые правила. Пользовательские корректировки категорий сохраняются в SQLite. Автоматически присвоенные категории не используются как истинная разметка ML-модели. Детектор серий требует не менее трёх согласующихся наблюдений; подтверждение пользователя хранится отдельно. Будущие события поддерживают создание, изменение статуса, отмену и CSV-импорт. Налоги не рассчитываются без пользовательских исходных данных. Учитываются только ожидаемые/подтверждённые события, совпадающие с регулярной серией платежи не добавляются дважды.

Прогноз строится отдельно для компании на 30/60/90 дней. Сравниваются baseline и HistGradientBoosting, если для компании достаточно истории; модель выбирается по временному walk-forward backtesting. Метрики потоков: MAE, RMSE, WAPE; накопленная ошибка остатка отдельно доступна на горизонтах 7/30/90 дней. Риск оценивается детерминированным пересечением порога резерва, а при наличии не менее 30 out-of-sample остатков ошибок — блочным bootstrap с блоками последовательных дней. При малом объёме ошибок вероятность не показывается.

Архитектура backend/frontend и методика расчётов: [docs/architecture.md](./docs/architecture.md), [docs/methodology.md](./docs/methodology.md).

## Требования

- Python 3.11+ (совместимость проверялась на Python 3.14).
- Node.js 20.19+ и npm 10+ (Vite 7).
- Windows PowerShell, macOS или Linux.

## Установка и запуск

Команды запускайте из **корня проекта** — папки с этим README, в двух отдельных терминалах. Backend загружает датасет один раз при запуске; после замены CSV перезапустите backend. Если задаёте `CASHFLOW_DATA_DIR` вручную, укажите абсолютный путь к `data\dataset` либо относительный `data\dataset`. Конфигурация также распознаёт старое `..\data\dataset`, заданное для запуска из `backend/`, и при запуске из корня ищет набор рядом с backend.

### Windows PowerShell

Терминал 1 — backend (из корня проекта):

```powershell
$projectRoot = (Get-Location).Path
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:CASHFLOW_DATA_DIR = (Join-Path $projectRoot "data\dataset")
$env:CASHFLOW_DATABASE = (Join-Path $projectRoot "backend\data\cashflow.sqlite3")
$env:CASHFLOW_FRONTEND_ORIGINS = "http://localhost:5173"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Терминал 2 — frontend (из корня проекта):

```powershell
Set-Location frontend
npm install
$env:VITE_API_URL = "http://127.0.0.1:8000/api"
npm run dev
```

Откройте `http://localhost:5173`. Backend: `http://127.0.0.1:8000`; Swagger/OpenAPI: `http://127.0.0.1:8000/docs`; состояние и информация о датасете: `http://127.0.0.1:8000/api/health`.

Если frontend сообщает, что backend недоступен, откройте `http://127.0.0.1:8000/api/health`. Для загруженного датасета ответ должен содержать `"status":"ready"`, `"data_available":true`, число компаний и операций. Проверьте, что frontend использует тот же адрес API (`VITE_API_URL`) и что сервер запущен на порту `8000`.

### Linux/macOS

Терминал 1 — backend (из корня проекта):

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
export CASHFLOW_DATA_DIR="$PWD/data/dataset"
export CASHFLOW_DATABASE="$PWD/backend/data/cashflow.sqlite3"
export CASHFLOW_FRONTEND_ORIGINS=http://localhost:5173
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Терминал 2 — frontend (из корня проекта):

```bash
cd frontend
npm install
export VITE_API_URL=http://127.0.0.1:8000/api
npm run dev
```

Примеры переменных также находятся в `backend/.env.example` и `frontend/.env.example`. Значения из `.env.example` нужно задать оболочке либо скопировать в локальный `.env`; секретов приложение не требует.

## Проверка

Backend тесты (из `backend/` после установки его зависимостей):

```powershell
python -m pytest -q
```

Frontend тесты и production-сборка (из `frontend/`):

```powershell
npm test
npm run build
```

Тесты backend и общей Python-бизнес-логики запускаются из корня после установки зависимостей backend: `python -m pytest -q backend/tests tests`.

## API

- `GET /api/health`
- `GET /api/companies`, `/api/companies/overview`, `GET /api/companies/{id}`
- `GET /api/companies/{id}/operations` — фильтры и серверная пагинация, максимум 200 строк на страницу
- `GET /api/companies/{id}/summary`, `/categories`, `/recurring`, `/forecast`, `/risks`, `/model-evaluation`
- `GET/POST /api/companies/{id}/events`
- `PATCH/DELETE /api/companies/{id}/events/{event_id}` (DELETE переводит запись в статус «Отменено»)
- `POST /api/companies/{id}/events/import` (CSV)
- `PATCH /api/companies/{id}/operations/{operation_id}/category`
- `PATCH /api/companies/{id}/recurring/{recurring_id}`

## Настройка нового источника данных

1. Убедитесь, что CSV распакованы локально в `data/dataset/`.
2. Проверьте заголовки полей: `companies.csv` должен содержать `company_id`, наименование, ИНН, ОПФ, отрасль; операции — `company_id`, `operation_id`, `operation_date`, `amount`, `direction`, `counterparty_inn`, `counterparty_name`, `payment_purpose`, `balance_eod`.
3. Перезапустите backend. Ошибки/число строк и путь источника доступны в `GET /api/health`.
4. Сверьте сохранённые остатки, даты и несколько ИНН с исходным CSV, затем проверьте метрики и категории компании.
5. Если данные размещены в другом каталоге, задайте `CASHFLOW_DATA_DIR` до запуска backend.

## Ограничения и устранение проблем

- **Путь в `/api/health` заканчивается на `pet projects\data\dataset`:** в текущем PowerShell выполните `$env:CASHFLOW_DATA_DIR = (Join-Path (Get-Location).Path "data\dataset")`, остановите старый backend и запустите его снова. Либо удалите переопределение командой `Remove-Item Env:CASHFLOW_DATA_DIR`; тогда будет использован `autumnHak\data\dataset`.
- **Нет компаний/операций:** проверьте `data_directory`, `companies` и `operations` в `/api/health`; после замены CSV перезапустите backend.
- **Ошибка кодировки/разделителя:** поддержан заявленный формат UTF-8 BOM + `;`. Исправьте исходный CSV на этот формат; не открывайте и не пересохраняйте ИНН как числа.
- **Не запускается FastAPI:** из корня проекта активируйте `backend/.venv`, установите `python -m pip install -r backend/requirements.txt` и запускайте Uvicorn с `--app-dir backend`, как в командах выше.
- **Frontend сообщает, что API недоступен:** проверьте, что backend запущен на `127.0.0.1:8000`, откройте `http://127.0.0.1:8000/api/health` и убедитесь, что `VITE_API_URL` задан как `http://127.0.0.1:8000/api`. Если меняли `.env`, перезапустите Vite.
- **Занят порт 8000/5173:** остановите процесс, занимающий порт, либо задайте другой порт Vite/Uvicorn и соответствующий CORS origin / `VITE_API_URL`.
- **CORS:** origin frontend по умолчанию `http://localhost:5173`; измените `CASHFLOW_FRONTEND_ORIGINS`, если используете другой адрес.
- **Несовместимый Node/Vite:** используйте Node.js не ниже 20.19 и повторите `npm install`.
- **Нет вероятностной оценки:** это ожидаемое поведение при менее чем 30 out-of-sample ошибках.
- **Синтетические примеры:** CSV в `data/demo/` используются только в тестах Python-бизнес-логики; API не использует их как fallback.

Реальные банковские, налоговые и бухгалтерские API не подключены. Перед оценкой на настоящих компаниях необходимо подтвердить формат и полноту выписки, календарь остатка, валюту и смысл направлений.
