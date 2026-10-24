"""Explainable keyword-based categorization rules."""

from config.settings import DEFAULT_CATEGORIES

RULES = (
    ("Переводы между собственными счетами", ("между своими счетами", "перевод себе", "собственный счет")),
    ("Фонд оплаты труда", ("заработная плата", "зарплата", "аванс сотруд", "фонд оплаты труда")),
    ("Налоги и обязательные платежи", ("налог", "ифнс", "фнс", "страховой взнос", "пенсион")),
    ("Аренда", ("аренд", "арендная плата")),
    ("Комиссии банка", ("комиссия", "обслуживание счета", "банковское обслуживание")),
    ("Кредиты и проценты", ("кредит", "процент по займу", "погашение займа")),
    ("Маркетинг и реклама", ("реклам", "маркетинг", "продвижение")),
    ("Логистика и транспорт", ("доставка", "логист", "транспорт", "такси", "топливо")),
    ("Оборудование и капитальные расходы", ("оборудован", "основное средство", "компьютер")),
    ("Закупки и поставщики", ("поставка", "закуп", "товар", "материал", "поставщик")),
)


def categorize_rule(operation: dict | object) -> dict[str, object]:
    """Classify a single operation and return an explanation and confidence."""
    get = operation.get if isinstance(operation, dict) else lambda key, default="": getattr(operation, key, default)
    text = " ".join(str(get(key, "")) for key in ("purpose", "counterparty", "inn")).lower()
    amount = float(get("amount", 0) or 0)
    if "поступлен" in text or "оплата от клиента" in text or "выручка" in text:
        category, confidence = "Выручка и поступления от клиентов", 0.9
    else:
        category, confidence = "", 0.0
        for candidate, words in RULES:
            if any(word in text for word in words):
                category, confidence = candidate, 0.85
                break
    if not category and amount > 0:
        category, confidence = "Прочие поступления", 0.62
    elif not category and amount < 0:
        category, confidence = "Прочие расходы", 0.62
    needs_review = confidence < 0.65
    if needs_review:
        category = "Требует проверки"
    return {"category": category, "method": "правила", "confidence": confidence, "needs_review": needs_review}


def available_categories() -> tuple[str, ...]:
    return DEFAULT_CATEGORIES
