"""Explainable transaction categorization with persistent user corrections."""

from __future__ import annotations

import pandas as pd

from app.core.storage import SQLiteStore
from src.categorization.rules import categorize_rule


def categorize_operations(frame: pd.DataFrame, store: SQLiteStore) -> pd.DataFrame:
    """Categorize a single company's records and apply saved overrides."""
    result = frame.drop(columns=["category"], errors="ignore").copy()
    if result.empty:
        for column in ("category", "category_method", "confidence", "needs_review"):
            result[column] = pd.Series(dtype="object")
        return result
    classifications = result.apply(categorize_rule, axis=1, result_type="expand")
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
