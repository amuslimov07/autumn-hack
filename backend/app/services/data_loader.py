"""Load the case dataset once and normalize bank operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import DATA_DIR

LOGGER = logging.getLogger(__name__)
OPERATION_ALIASES = {
    "company_id": ("company_id", "идентификатор компании", "id компании"),
    "operation_id": ("operation_id", "идентификатор операции", "id операции"),
    "operation_date": ("operation_date", "дата операции", "дата"),
    "amount": ("amount", "сумма"),
    "direction": ("direction", "направление"),
    "counterparty_inn": ("counterparty_inn", "инн контрагента"),
    "counterparty_name": ("counterparty_name", "контрагент"),
    "payment_purpose": ("payment_purpose", "назначение платежа"),
    "balance_eod": ("balance_eod", "остаток на конец дня", "остаток"),
    "event_type": ("event_type", "тип события"),
}
COMPANY_ALIASES = {
    "company_id": ("company_id", "идентификатор компании", "id компании"),
    "name": ("name", "company_name", "название", "наименование"),
    "inn": ("inn", "company_inn", "инн"),
    "legal_form": ("legal_form", "organizational_form", "организационно-правовая форма", "опф"),
    "industry": ("industry", "activity", "вид деятельности", "отрасль"),
    "first_operation_date": ("first_operation_date", "дата первой операции"),
    "last_operation_date": ("last_operation_date", "дата последней операции"),
}
REQUIRED_OPERATIONS = ("company_id", "operation_id", "operation_date", "amount", "direction", "balance_eod")


def _column_map(columns: list[object], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    lookup = {str(column).strip().lower().replace("ё", "е"): str(column) for column in columns}
    result = {}
    for target, variants in aliases.items():
        for variant in variants:
            column = lookup.get(variant.lower().replace("ё", "е"))
            if column is not None:
                result[target] = column
                break
    return result


def read_csv(path: Path, dtypes: dict[str, str] | None = None) -> pd.DataFrame:
    """Read the case CSV format with BOM, semicolon and string identifiers."""
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=dtypes, low_memory=False)


@dataclass
class Dataset:
    companies: pd.DataFrame
    operations: pd.DataFrame
    status: str
    message: str
    errors: list[str]

    def company_operations(self, company_id: str) -> pd.DataFrame:
        if self.operations.empty:
            return self.operations.copy()
        return self.operations.loc[self.operations["company_id"] == str(company_id)].copy()

    def company(self, company_id: str) -> dict | None:
        rows = self.companies.loc[self.companies["company_id"] == str(company_id)]
        return None if rows.empty else rows.iloc[0].to_dict()


def load_dataset(data_dir: Path = DATA_DIR) -> Dataset:
    """Load company catalog and either combined OR per-company statements."""
    companies_path = data_dir / "companies.csv"
    combined_path = data_dir / "all_operations.csv"
    statements_dir = data_dir / "statements"
    errors: list[str] = []
    if not companies_path.is_file():
        return Dataset(pd.DataFrame(), pd.DataFrame(), "missing", f"Не найден справочник компаний: {companies_path}", errors)
    try:
        raw_companies = read_csv(companies_path, {"company_id": "string", "inn": "string", "company_inn": "string"})
        company_map = _column_map(list(raw_companies.columns), COMPANY_ALIASES)
        if "company_id" not in company_map:
            raise ValueError("В companies.csv отсутствует company_id.")
        companies = raw_companies.rename(columns={value: key for key, value in company_map.items()})
        companies["company_id"] = companies["company_id"].astype("string").str.strip()
        for column in ("name", "inn", "legal_form", "industry", "first_operation_date", "last_operation_date"):
            if column not in companies:
                companies[column] = ""
        companies["name"] = companies["name"].fillna(companies["company_id"]).astype(str)
        companies["inn"] = companies["inn"].fillna("").astype(str)
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as error:
        LOGGER.exception("Unable to load company catalog from %s", companies_path)
        return Dataset(pd.DataFrame(), pd.DataFrame(), "invalid", f"Ошибка чтения справочника компаний: {error}", [str(error)])

    try:
        if combined_path.is_file():
            operations = _load_operations_file(combined_path)
        elif statements_dir.is_dir():
            frames = []
            for statement_path in sorted(statements_dir.glob("C*.csv")):
                try:
                    frames.append(_load_operations_file(statement_path))
                except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as error:
                    errors.append(f"{statement_path.name}: {error}")
            operations = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        else:
            return Dataset(companies, pd.DataFrame(), "incomplete",
                           f"Не найдены all_operations.csv или каталог statements в {data_dir}.", errors)
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as error:
        LOGGER.exception("Unable to load operations from %s", data_dir)
        return Dataset(companies, pd.DataFrame(), "invalid", f"Ошибка чтения операций: {error}", [*errors, str(error)])

    if operations.empty:
        return Dataset(companies, operations, "incomplete", "Файлы операций пусты или отсутствуют.", errors)
    operations = operations.drop_duplicates(["company_id", "operation_id"], keep="first")
    known_ids = set(companies["company_id"].astype(str))
    operations = operations.loc[operations["company_id"].astype(str).isin(known_ids)].copy()
    companies = companies.drop_duplicates("company_id", keep="first").reset_index(drop=True)
    status = "ready" if len(companies) else "incomplete"
    return Dataset(companies, operations.reset_index(drop=True), status,
                   f"Загружено компаний: {len(companies)}; операций: {len(operations)}.", errors)


def _load_operations_file(path: Path) -> pd.DataFrame:
    raw = read_csv(path, {"company_id": "string", "operation_id": "string", "counterparty_inn": "string"})
    mapped = _column_map(list(raw.columns), OPERATION_ALIASES)
    missing = [field for field in REQUIRED_OPERATIONS if field not in mapped]
    if missing:
        if "company_id" not in mapped and path.parent.name == "statements":
            raw["company_id"] = path.stem
            mapped["company_id"] = "company_id"
            missing.remove("company_id")
        if missing:
            raise ValueError("Не хватает полей: " + ", ".join(missing))
    operations = raw.rename(columns={value: key for key, value in mapped.items()}).copy()
    if "operation_id" not in operations:
        operations["operation_id"] = [f"{path.stem}-{index}" for index in range(len(operations))]
    operations["company_id"] = operations["company_id"].astype("string").str.strip()
    operations["operation_id"] = operations["operation_id"].astype("string").str.strip()
    operations["operation_date"] = pd.to_datetime(operations["operation_date"], errors="coerce")
    operations["amount"] = pd.to_numeric(operations["amount"], errors="coerce").abs()
    direction = operations["direction"].astype("string").str.strip().str.lower()
    incoming = direction.isin(["поступление", "поступление ", "income", "credit"])
    outgoing = direction.isin(["списание", "расход", "expense", "debit"])
    invalid_direction = ~(incoming | outgoing)
    if invalid_direction.any():
        raise ValueError(f"Неизвестное направление в {int(invalid_direction.sum())} строках.")
    operations["signed_amount"] = operations["amount"].where(incoming, -operations["amount"])
    operations["balance_eod"] = pd.to_numeric(operations["balance_eod"], errors="coerce")
    for field in ("counterparty_inn", "counterparty_name", "payment_purpose"):
        if field not in operations:
            operations[field] = ""
        operations[field] = operations[field].fillna("").astype("string").str.strip()
    operations = operations.dropna(subset=["company_id", "operation_id", "operation_date", "amount", "balance_eod"])
    operations = operations.loc[operations["amount"] > 0]
    operations["date"] = operations["operation_date"].dt.normalize()
    operations["account"] = operations["company_id"].astype(str)
    operations["counterparty"] = operations["counterparty_name"].astype(str)
    operations["inn"] = operations["counterparty_inn"].astype(str)
    operations["purpose"] = operations["payment_purpose"].astype(str)
    operations["amount"] = operations["signed_amount"]
    operations["balance"] = operations["balance_eod"]
    operations["direction"] = operations["signed_amount"].gt(0).map({True: "поступление", False: "списание"})
    operations["source_row_id"] = operations["operation_id"].astype(str)
    return operations.reset_index(drop=True)


def validate_daily_balances(operations: pd.DataFrame) -> pd.DataFrame:
    """One EOD balance per date and day opening balances from signed transaction sums."""
    if operations.empty:
        return pd.DataFrame(columns=["company_id", "date", "net_flow", "closing_balance", "opening_balance", "operations"])
    grouped = operations.groupby(["company_id", "date"], as_index=False).agg(
        net_flow=("signed_amount", "sum"),
        closing_balance=("balance_eod", "last"),
        operations=("operation_id", "count"),
    ).sort_values(["company_id", "date"])
    grouped["opening_balance"] = grouped["closing_balance"] - grouped["net_flow"]
    previous_close = grouped.groupby("company_id")["closing_balance"].shift()
    consecutive = grouped.groupby("company_id")["date"].diff().dt.days.eq(1)
    grouped["balance_consistent"] = (~consecutive) | (
        (grouped["closing_balance"] - previous_close - grouped["net_flow"]).abs() < 0.01
    )
    return grouped.reset_index(drop=True)
