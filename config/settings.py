"""Shared application settings."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT_DIR / "data" / "demo"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
RANDOM_SEED = 42
DEFAULT_HORIZON_DAYS = 90
MINIMUM_HISTORY_DAYS_FOR_ML = 120
DEFAULT_CATEGORIES = (
    "Выручка и поступления от клиентов",
    "Закупки и поставщики",
    "Фонд оплаты труда",
    "Налоги и обязательные платежи",
    "Аренда",
    "Маркетинг и реклама",
    "Логистика и транспорт",
    "Комиссии банка",
    "Кредиты и проценты",
    "Оборудование и капитальные расходы",
    "Переводы между собственными счетами",
    "Прочие поступления",
    "Прочие расходы",
    "Требует проверки",
)
