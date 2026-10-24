"""Company, operation, forecast, risk and future-event routes."""

from __future__ import annotations

import io
from datetime import date

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from config.settings import DEFAULT_CATEGORIES
from app.schemas.api import CategoryPatch, EventCreate, EventPatch, RecurringPatch
from app.services.categorization import categorize_operations
from app.services.data_loader import validate_daily_balances
from app.services.forecasting import calculate_forecast, category_summary, evaluation_payload
from app.services.recurring import company_recurring
from src.data.loader import detect_columns, parse_money

router = APIRouter(prefix="/api")
VALID_CATEGORIES = DEFAULT_CATEGORIES


def _json_value(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    return [{key: _json_value(value) for key, value in row.items()} for row in frame.to_dict("records")]


def _context(request: Request, company_id: str):
    dataset = request.app.state.dataset
    company = dataset.company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Компания не найдена в загруженном справочнике.")
    if dataset.operations.empty:
        raise HTTPException(status_code=503, detail="Датасет операций недоступен. Проверьте файлы companies.csv и all_operations.csv.")
    operations = dataset.company_operations(company_id)
    if operations.empty:
        raise HTTPException(status_code=404, detail="Для компании нет доступных операций.")
    return dataset, company, operations, request.app.state.store


@router.get("/health")
def health(request: Request):
    dataset = request.app.state.dataset
    return {
        "status": dataset.status,
        "data_available": not dataset.operations.empty,
        "companies": len(dataset.companies),
        "operations": len(dataset.operations),
        "data_directory": str(request.app.state.data_directory),
        "message": dataset.message,
        "errors": dataset.errors[:20],
    }


@router.get("/companies")
def companies(
    request: Request,
    search: str | None = None,
    industry: str | None = None,
    legal_form: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    frame = request.app.state.dataset.companies.copy()
    if not frame.empty:
        if search:
            query = search.casefold()
            mask = frame["company_id"].astype(str).str.casefold().str.contains(query, regex=False)
            mask |= frame["name"].astype(str).str.casefold().str.contains(query, regex=False)
            mask |= frame["inn"].astype(str).str.casefold().str.contains(query, regex=False)
            frame = frame.loc[mask]
        if industry:
            frame = frame.loc[frame["industry"].astype(str).str.contains(industry, case=False, regex=False)]
        if legal_form:
            frame = frame.loc[frame["legal_form"].astype(str).str.contains(legal_form, case=False, regex=False)]
    total = len(frame)
    result = frame.iloc[(page - 1) * page_size:page * page_size]
    return {"items": _records(result), "total": total, "page": page, "page_size": page_size}


@router.get("/companies/overview")
def companies_overview(request: Request):
    dataset = request.app.state.dataset
    companies_frame = dataset.companies
    operations = dataset.operations
    if companies_frame.empty:
        return {"companies": 0, "operations": 0, "rows": []}
    rows = []
    latest_by_company = {}
    operation_counts = operations.groupby("company_id").size().to_dict() if not operations.empty else {}
    if not operations.empty:
        latest_days = operations.groupby("company_id")["date"].max()
        for company_id, last_date in latest_days.items():
            last_rows = operations.loc[(operations["company_id"] == company_id) & (operations["date"] == last_date)]
            last = last_rows.iloc[-1]
            latest_by_company[str(company_id)] = {"date": last_date, "balance": last["balance_eod"]}
    for company in companies_frame.to_dict("records"):
        company_id = str(company["company_id"])
        last = latest_by_company.get(company_id)
        rows.append({
            **{key: _json_value(value) for key, value in company.items()},
            "operation_count": int(operation_counts.get(company_id, 0)),
            "last_balance": None if last is None else _json_value(last["balance"]),
            "balance_date": None if last is None else _json_value(last["date"]),
        })
    return {"companies": len(rows), "operations": len(operations), "rows": rows}


@router.get("/companies/{company_id}")
def company_detail(company_id: str, request: Request):
    dataset = request.app.state.dataset
    company = dataset.company(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Компания не найдена.")
    result = {key: _json_value(value) for key, value in company.items()}
    result["operation_count"] = int(dataset.operations.groupby("company_id").size().get(company_id, 0)) if not dataset.operations.empty else 0
    return result


@router.get("/companies/{company_id}/operations")
def operations(
    company_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    direction: str | None = Query(default=None, pattern="^(поступление|списание)$"),
    counterparty: str | None = None,
    search: str | None = None,
    sort: str = Query(default="operation_date"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    _, _, frame, store = _context(request, company_id)
    if start_date:
        frame = frame.loc[frame["date"] >= pd.Timestamp(start_date)]
    if end_date:
        frame = frame.loc[frame["date"] <= pd.Timestamp(end_date)]
    if direction:
        frame = frame.loc[frame["direction"] == direction]
    if counterparty:
        frame = frame.loc[frame["counterparty_name"].str.contains(counterparty, case=False, regex=False, na=False)]
    if search:
        frame = frame.loc[
            frame["counterparty_name"].str.contains(search, case=False, regex=False, na=False) |
            frame["payment_purpose"].str.contains(search, case=False, regex=False, na=False)
        ]
    categorized = categorize_operations(frame, store)
    if category:
        categorized = categorized.loc[categorized["category"] == category]
    allowed_sort = {"operation_date", "amount", "counterparty_name", "operation_id", "category"}
    if sort not in allowed_sort:
        raise HTTPException(status_code=422, detail=f"Сортировка по {sort!r} не поддерживается.")
    total = len(categorized)
    ordered = categorized.sort_values(sort, ascending=order == "asc", kind="stable")
    columns = ["operation_id", "company_id", "operation_date", "amount", "signed_amount", "direction",
               "counterparty_inn", "counterparty_name", "payment_purpose", "balance_eod", "category",
               "category_method", "confidence", "needs_review"]
    page_frame = ordered.iloc[(page - 1) * page_size:page * page_size][columns]
    return {"items": _records(page_frame), "total": total, "page": page, "page_size": page_size}


@router.get("/companies/{company_id}/summary")
def summary(
    company_id: str,
    request: Request,
    horizon: int = Query(default=90, json_schema_extra={"enum": [30, 60, 90]}),
    reserve: float = Query(default=0, ge=0),
):
    if horizon not in (30, 60, 90):
        raise HTTPException(status_code=422, detail="Горизонт прогноза должен быть 30, 60 или 90 дней.")
    _, company, frame, store = _context(request, company_id)
    forecast, details, risk = calculate_forecast(frame, company, store, horizon, reserve)
    balances = validate_daily_balances(frame)
    last = balances.iloc[-1]
    return {
        "company_id": company_id,
        "last_balance": _json_value(last["closing_balance"]),
        "balance_date": _json_value(last["date"]),
        "balance_is_current": bool(pd.Timestamp(last["date"]).normalize() >= pd.Timestamp.today().normalize()),
        "forecast_balance_7": _json_value(forecast.iloc[min(6, len(forecast) - 1)]["balance"]),
        "forecast_balance_30": _json_value(forecast.iloc[min(29, len(forecast) - 1)]["balance"]),
        "forecast_balance_90": _json_value(forecast.iloc[-1]["balance"]),
        "forecast_inflows": _json_value(forecast["inflow"].sum()),
        "forecast_outflows": _json_value(forecast["outflow"].sum()),
        "upcoming_obligations": int(sum(
            event["status"] in ("Ожидается", "Подтверждено")
            and event["direction"] == "списание"
            and pd.Timestamp(event["event_date"]) >= pd.Timestamp(forecast["date"].min())
            and pd.Timestamp(event["event_date"]) <= pd.Timestamp(forecast["date"].max())
            for event in store.list_events(company_id)
        )),
        "first_risk_date": _json_value(risk["first_breach"]),
        "max_deficit": _json_value(risk["max_deficit"]),
        "risk_level": risk["risk_level"],
        "risk_probability": risk["probability"],
        "selected_model": details["selected_method"],
        "history_days": int((frame["date"].max() - frame["date"].min()).days + 1),
        "observed_days": int(frame["date"].nunique()),
        "unobserved_calendar_days": int(max(0, (frame["date"].max() - frame["date"].min()).days + 1 - frame["date"].nunique())),
        "balance_consistency_errors": int((~balances["balance_consistent"]).sum()),
    }


@router.get("/companies/{company_id}/categories")
def categories(company_id: str, request: Request, start_date: date | None = None, end_date: date | None = None):
    _, _, frame, store = _context(request, company_id)
    summary_rows = category_summary(frame, store, start_date, end_date)
    monthly = categorize_operations(frame, store)
    monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
    monthly["flow_amount"] = monthly["signed_amount"].abs()
    trends = monthly.groupby(["month", "direction", "category"], as_index=False)["flow_amount"].sum()
    normalized_summary = {
        direction: _records(pd.DataFrame(rows)) if rows else []
        for direction, rows in summary_rows.items()
    }
    return {"by_direction": normalized_summary, "monthly": _records(trends)}


@router.get("/companies/{company_id}/recurring")
def recurring(company_id: str, request: Request):
    _, _, frame, store = _context(request, company_id)
    rows = company_recurring(categorize_operations(frame, store), store)
    return {"items": _records(rows)}


@router.get("/companies/{company_id}/forecast")
def forecast(
    company_id: str,
    request: Request,
    horizon: int = Query(default=90, json_schema_extra={"enum": [30, 60, 90]}),
    reserve: float = Query(default=0, ge=0),
    scenarios: int = Query(default=1000, ge=100, le=10000),
):
    if horizon not in (30, 60, 90):
        raise HTTPException(status_code=422, detail="Горизонт прогноза должен быть 30, 60 или 90 дней.")
    _, company, frame, store = _context(request, company_id)
    result, details, risk = calculate_forecast(frame, company, store, horizon, reserve, scenarios)
    daily_history = frame.groupby("date", as_index=False).agg(
        balance=("balance_eod", "last"),
        inflow=("signed_amount", lambda values: values[values > 0].sum()),
        outflow=("signed_amount", lambda values: -values[values < 0].sum()),
    )
    return {
        "company_id": company_id, "horizon": horizon,
        "balance_date": _json_value(frame.loc[frame["balance"].notna(), "date"].max() if frame["balance"].notna().any() else None),
        "balance_source": details["balance_source"],
        "method": details["forecast_method"], "selected_model": details["selected_method"],
        "items": _records(result),
        "history": _records(daily_history),
        "uncertainty_note": "Дни без операций не доказывают нулевой поток; прогноз помечен как неопределённый, когда в истории есть календарные пробелы.",
        "risk": {key: _json_value(value) for key, value in risk.items() if key not in {"warning", "influencing_events"}},
        "warning": _records(pd.DataFrame([risk["warning"]]))[0] if risk.get("warning") else None,
        "influencing_events": risk.get("influencing_events", []),
    }


@router.get("/companies/{company_id}/risks")
def risks(
    company_id: str,
    request: Request,
    horizon: int = Query(default=90, json_schema_extra={"enum": [30, 60, 90]}),
    reserve: float = Query(default=0, ge=0),
):
    if horizon not in (30, 60, 90):
        raise HTTPException(status_code=422, detail="Горизонт прогноза должен быть 30, 60 или 90 дней.")
    result = forecast(company_id, request, horizon, reserve, scenarios=1000)
    risk = result["risk"]
    return {"risk": risk, "warning": result["warning"], "influencing_events": result["influencing_events"],
            "method": risk["method"], "horizon_days": horizon}


@router.get("/companies/{company_id}/model-evaluation")
def model_evaluation(company_id: str, request: Request):
    _, company, frame, store = _context(request, company_id)
    _, details, _ = calculate_forecast(frame, company, store, 90, 0)
    return evaluation_payload(details)


@router.get("/companies/{company_id}/events")
def events(company_id: str, request: Request, include_cancelled: bool = False):
    _context(request, company_id)
    return {"items": [_json_event(event) for event in request.app.state.store.list_events(company_id, include_cancelled)]}


def _json_event(event: dict) -> dict:
    item = dict(event)
    item["event_date"] = item.pop("event_date")
    item["date"] = item["event_date"]
    item["direction"] = item["direction"]
    return {key: _json_value(value) for key, value in item.items()}


@router.post("/companies/{company_id}/events", status_code=201)
def create_event(company_id: str, payload: EventCreate, request: Request):
    _context(request, company_id)
    return _json_event(request.app.state.store.create_event(company_id, payload.model_dump()))


@router.patch("/companies/{company_id}/events/{event_id}")
def update_event(company_id: str, event_id: int, payload: EventPatch, request: Request):
    _context(request, company_id)
    updated = request.app.state.store.update_event(company_id, event_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Будущее событие не найдено.")
    return _json_event(updated)


@router.delete("/companies/{company_id}/events/{event_id}")
def cancel_event(company_id: str, event_id: int, request: Request):
    _context(request, company_id)
    updated = request.app.state.store.cancel_event(company_id, event_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Будущее событие не найдено.")
    return _json_event(updated)


@router.post("/companies/{company_id}/events/import")
async def import_events(company_id: str, request: Request, file: UploadFile = File(...)):
    _context(request, company_id)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Импорт событий поддерживает CSV.")
    try:
        raw = pd.read_csv(io.BytesIO(await file.read()), sep=None, engine="python", encoding="utf-8-sig")
        columns = detect_columns(list(raw.columns))
        required = [field for field in ("date", "amount", "direction") if field not in columns]
        if required:
            raise ValueError("Нужны столбцы даты, суммы и направления.")
        created = []
        for row in raw.to_dict("records"):
            date_value = pd.to_datetime(row[columns["date"]], dayfirst=True, errors="raise").date()
            amount = abs(parse_money(row[columns["amount"]]))
            direction_text = str(row[columns["direction"]]).strip().lower()
            if direction_text in ("поступление", "income", "credit"):
                direction = "поступление"
            elif direction_text in ("списание", "расход", "expense", "debit"):
                direction = "списание"
            else:
                raise ValueError(f"Неизвестное направление: {direction_text}")
            record = {
                "date": date_value, "amount": amount, "direction": direction,
                "category": str(row.get(columns.get("category", ""), "Прочие расходы")),
                "event_type": str(row.get(columns.get("event_type", ""), "импортированное событие")),
                "description": str(row.get(columns.get("description", ""), "")),
                "source": file.filename, "status": "Ожидается",
            }
            from app.schemas.api import EventCreate
            created.append(request.app.state.store.create_event(company_id, EventCreate(**record).model_dump()))
        return {"imported": len(created), "items": [_json_event(item) for item in created]}
    except (ValueError, TypeError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise HTTPException(status_code=422, detail=f"Не удалось импортировать события: {error}") from error


@router.patch("/companies/{company_id}/operations/{operation_id}/category")
def change_category(company_id: str, operation_id: str, payload: CategoryPatch, request: Request):
    _, _, frame, store = _context(request, company_id)
    if operation_id not in set(frame["operation_id"].astype(str)):
        raise HTTPException(status_code=404, detail="Операция не найдена.")
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail="Недопустимая категория.")
    store.set_category(company_id, operation_id, payload.category)
    return {"company_id": company_id, "operation_id": operation_id, "category": payload.category, "saved": True}


@router.patch("/companies/{company_id}/recurring/{recurring_id}")
def update_recurring(company_id: str, recurring_id: str, payload: RecurringPatch, request: Request):
    _, _, frame, store = _context(request, company_id)
    items = company_recurring(categorize_operations(frame, store), store)
    if items.empty or recurring_id not in set(items["recurring_id"]):
        raise HTTPException(status_code=404, detail="Регулярная серия не найдена.")
    store.set_recurring(company_id, recurring_id, payload.confirmed)
    return {"company_id": company_id, "recurring_id": recurring_id, "confirmed": payload.confirmed}
