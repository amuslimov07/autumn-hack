"""Explainable transaction categorization with persistent user corrections."""

from __future__ import annotations

import logging

import pandas as pd

from app.core.storage import SQLiteStore
from src.categorization.rules import categorize_rule

LOGGER = logging.getLogger(__name__)


def _fallback_category(operation: pd.Series) -> dict[str, object]:
    direction = str(operation.get("direction", "") or "").strip().casefold()
    incoming = direction in {"поступление", "поступления", "income", "credit", "входящий"}
    if direction not in {"поступление", "поступления", "income", "credit", "входящий",
                         "списание", "расход", "расходы", "expense", "debit", "исходящий"}:
        try:
            incoming = float(operation.get("signed_amount", operation.get("amount", 0)) or 0) > 0
        except (TypeError, ValueError, OverflowError):
            incoming = False
    return {
        "category": "Прочие поступления" if incoming else "Прочие расходы",
        "method": "резервная категория",
        "confidence": 0.0,
        "needs_review": False,
    }


def _categorize_safely(operation: pd.Series) -> dict[str, object]:
    try:
        result = categorize_rule(operation)
    except Exception:
        LOGGER.exception("Operation categorization failed for %s", operation.get("operation_id", "<unknown>"))
        return _fallback_category(operation)
    if not str(result.get("category", "")).strip():
        LOGGER.error("Categorization returned an empty category for %s", operation.get("operation_id", "<unknown>"))
        return _fallback_category(operation)
    return result


def categorize_operations(frame: pd.DataFrame, store: SQLiteStore) -> pd.DataFrame:
    """Categorize a single company's records and apply saved overrides."""
    result = frame.drop(columns=["category"], errors="ignore").copy()
    if result.empty:
        for column in ("category", "category_method", "confidence", "needs_review"):
            result[column] = pd.Series(dtype="object")
        return result
    classifications = result.apply(_categorize_safely, axis=1, result_type="expand")
    result = pd.concat([result, classifications.rename(columns={
        "method": "category_method", "confidence": "confidence", "needs_review": "needs_review",
    })], axis=1)
    overrides = store.get_category_overrides(str(result["company_id"].iloc[0]))
    mask = result["operation_id"].astype(str).isin(overrides)
    result.loc[mask, "category"] = result.loc[mask, "operation_id"].astype(str).map(overrides)
    result.loc[mask, "category_method"] = "ручная корректировка"
    result.loc[mask, "confidence"] = 1.0
    result.loc[mask, "needs_review"] = False
    return result
