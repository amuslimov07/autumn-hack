from src.categorization.rules import categorize_rule
from src.categorization.classifier import categorize_operations
import pandas as pd


def test_rules_categorize_rent_and_uncertain_operation():
    rent = categorize_rule({"amount": -1000, "purpose": "Арендная плата", "counterparty": "БЦ"})
    unknown = categorize_rule({"amount": -1000, "purpose": "прочее", "counterparty": ""})
    assert rent["category"] == "Аренда"
    assert unknown["category"] == "Прочие расходы"
    assert not unknown["needs_review"]


def test_client_revenue_rule():
    result = categorize_rule({"amount": 500, "purpose": "Оплата от клиента за услуги"})
    assert result["category"] == "Выручка и поступления от клиентов"


def test_category_uses_operation_direction_and_russian_payment_variants():
    incoming = categorize_rule({
        "direction": "поступление", "amount": 1250, "purpose": "Оплата по договору",
        "counterparty": "Заказчик",
    })
    customer_inflow = categorize_rule({
        "direction": "поступление", "amount": 1250, "purpose": "",
        "counterparty": "Покупатель",
    })
    outgoing = categorize_rule({
        "direction": "списание", "amount": 1250, "purpose": "Оплата по договору",
        "counterparty": "Получатель",
    })
    salary = categorize_rule({"direction": "списание", "purpose": "Перечисление зарплаты сотрудникам"})
    salary_variant = categorize_rule({"direction": "списание", "purpose": "Выплата ЗП"})
    rent = categorize_rule({"direction": "списание", "purpose": "Арендная плата за помещение"})
    assert incoming["category"] == "Выручка и поступления от клиентов"
    assert customer_inflow["category"] == "Выручка и поступления от клиентов"
    assert outgoing["category"] == "Прочие расходы"
    assert salary["category"] == salary_variant["category"] == "Фонд оплаты труда"
    assert rent["category"] == "Аренда"


def test_unknown_operation_gets_fallback_category_for_its_direction():
    incoming = categorize_rule({"direction": "поступление", "purpose": "Неизвестная транзакция"})
    outgoing = categorize_rule({"direction": "списание", "purpose": "Неизвестная транзакция"})
    assert incoming["category"] == "Прочие поступления"
    assert outgoing["category"] == "Прочие расходы"
    assert not incoming["needs_review"] and not outgoing["needs_review"]


def test_user_labeled_examples_enable_classifier_without_fabricated_labels():
    frame = pd.DataFrame([
        {"date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i), "amount": -100.0,
         "purpose": "commercial premises monthly contract", "counterparty": "property operator", "inn": "",
         "category": "Аренда", "category_source": "manual"}
        for i in range(4)
    ] + [
        {"date": pd.Timestamp("2025-02-01") + pd.Timedelta(days=i), "amount": -200.0,
         "purpose": "bulk materials supplier invoice", "counterparty": "wholesale supplier", "inn": "",
         "category": "Закупки и поставщики", "category_source": "manual"}
        for i in range(4)
    ] + [
        {"date": pd.Timestamp("2025-03-01"), "amount": -300.0,
         "purpose": "commercial premises monthly invoice", "counterparty": "property operator", "inn": "",
         "category": "", "category_source": ""}
    ])
    categorized = categorize_operations(frame)
    assert categorized.iloc[-1]["category"] == "Аренда"
    assert categorized.iloc[-1]["method"] == "ML"
