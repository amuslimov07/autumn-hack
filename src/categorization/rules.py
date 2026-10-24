"""Explainable keyword-based categorization rules."""

import math
import re

from config.settings import DEFAULT_CATEGORIES

RULES = (
    ("Переводы между собственными счетами", (
        "между своими счетами", "между собственными счетами", "перевод себе",
        "перевод на свой счет", "перевод собственных средств",
    )),
    ("Фонд оплаты труда", (
        "заработн", "зарплат", "аванс сотруд", "выплата сотруд", "оплата труда",
        "фонд оплаты труда", "выплата зп", "зп", "фот", "реестр на выплату",
    )),
    ("Налоги и обязательные платежи", (
        "налог", "ифнс", "фнс", "енп", "ндфл", "ндс", "усн", "страховой взнос",
        "пенсион", "уплата в бюджет", "социальный взнос",
    )),
    ("Аренда", ("аренд",)),
    ("Комиссии банка", (
        "комисси", "обслуживание счета", "банковское обслуживание",
        "расчетно кассовое обслуживание", "рко",
    )),
    ("Кредиты и проценты", (
        "кредит", "процент по займу", "погашение займа", "погашение долга",
        "возврат займа",
    )),
    ("Лизинг", ("лизинг",)),
    ("Маркетинг и реклама", ("реклам", "маркетинг", "продвижение")),
    ("Логистика и транспорт", (
        "доставк", "логист", "транспорт", "такси", "топлив", "перевозк", "гсм",
    )),
    ("Оборудование и капитальные расходы", (
        "оборудован", "основное средство", "компьютер", "капитальн",
    )),
    ("Закупки и поставщики", (
        "поставк", "закуп", "товар", "материал", "поставщик", "сырье",
    )),
)

INCOME_DIRECTIONS = {"поступление", "поступления", "income", "credit", "входящий"}
EXPENSE_DIRECTIONS = {"списание", "расход", "расходы", "expense", "debit", "исходящий"}
INCOME_PURPOSES = (
    "выручк", "оплата от клиент", "оплата от покупател", "оплата покупател",
    "поступлен от покупател", "реализация", "за оказанные услуг", "оплат услуг",
    "оплат за услуг", "оплат за товар", "оплата по договор", "платеж по договор",
    "получение оплаты", "за оказанные работы", "за поставленный товар",
    "покупател", "заказчик", "клиент",
)


def _get(operation: dict | object, key: str, default: object = "") -> object:
    getter = getattr(operation, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(operation, key, default)


def _direction(operation: dict | object) -> bool:
    direction = str(_get(operation, "direction", "") or "").strip().casefold().replace("ё", "е")
    if direction in INCOME_DIRECTIONS:
        return True
    if direction in EXPENSE_DIRECTIONS:
        return False
    try:
        amount = float(_get(operation, "signed_amount", _get(operation, "amount", 0)) or 0)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(amount) and amount > 0


def _normalized_text(operation: dict | object) -> str:
    values = (_get(operation, key, "") for key in ("purpose", "counterparty", "inn"))
    text = " ".join(str(value) for value in values if value is not None)
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", text.casefold().replace("ё", "е"))).strip()


def categorize_rule(operation: dict | object) -> dict[str, object]:
    """Classify a single operation and return an explanation and confidence."""
    text = _normalized_text(operation)
    incoming = _direction(operation)
    if any(word in text for word in RULES[0][1]):
        category, confidence = RULES[0][0], 0.9
    elif incoming and any(word in text for word in INCOME_PURPOSES):
        category, confidence = "Выручка и поступления от клиентов", 0.9
    elif incoming:
        category, confidence = "Прочие поступления", 0.55
    else:
        category, confidence = "", 0.0
        for candidate, words in RULES[1:]:
            if any(word in text for word in words):
                category, confidence = candidate, 0.85
                break
        if not category:
            category, confidence = "Прочие расходы", 0.55
    needs_review = False
    return {"category": category, "method": "правила", "confidence": confidence, "needs_review": needs_review}


def available_categories() -> tuple[str, ...]:
    return DEFAULT_CATEGORIES
