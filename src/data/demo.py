"""Reproducible synthetic business statement for local demonstrations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import DEMO_DIR, RANDOM_SEED


def generate_demo_data(seed: int = RANDOM_SEED, days: int = 730) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create two years of synthetic transactions and near-term known events."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=days - 1)
    transactions: list[dict[str, object]] = []
    for date in pd.date_range(start, end, freq="D"):
        seasonal = 1.0 + 0.18 * np.sin(2 * np.pi * date.month / 12)
        if date.weekday() in (1, 3):
            for _ in range(int(rng.integers(1, 3))):
                transactions.append({
                    "Дата операции": date, "Сумма": round(float(rng.normal(48000, 15000) * seasonal), 2),
                    "Направление": "Поступление", "Контрагент": f"Клиент {int(rng.integers(1, 13)):02d}",
                    "ИНН контрагента": f"77{int(rng.integers(100000000, 999999999))}",
                    "Назначение платежа": "Оплата от клиента за услуги",
                })
        if date.day == 1:
            transactions.append({
                "Дата операции": date, "Сумма": 165000, "Направление": "Списание",
                "Контрагент": "БЦ Центральный", "ИНН контрагента": "7701000001",
                "Назначение платежа": "Арендная плата за офис",
            })
        if date.day == 5:
            transactions.append({
                "Дата операции": date, "Сумма": 520000, "Направление": "Списание",
                "Контрагент": "Сотрудники", "ИНН контрагента": "0000000000",
                "Назначение платежа": "Заработная плата сотрудникам",
            })
        if date.day == 15 and date.month in (1, 4, 7, 10):
            transactions.append({
                "Дата операции": date, "Сумма": 145000, "Направление": "Списание",
                "Контрагент": "ФНС", "ИНН контрагента": "7707329152",
                "Назначение платежа": "Налоговый платёж",
            })
        if date.day == 28:
            transactions.append({
                "Дата операции": date, "Сумма": 2400, "Направление": "Списание",
                "Контрагент": "Банк", "ИНН контрагента": "",
                "Назначение платежа": "Комиссия за обслуживание счета",
            })
        if date.weekday() == 2:
            transactions.append({
                "Дата операции": date, "Сумма": float(rng.normal(82000, 25000)), "Направление": "Списание",
                "Контрагент": f"Поставщик {int(rng.integers(1, 5))}", "ИНН контрагента": "7800000000",
                "Назначение платежа": "Поставка материалов",
            })
        if rng.random() < 0.035:
            is_income = rng.random() < 0.35
            transactions.append({
                "Дата операции": date, "Сумма": float(rng.uniform(15000, 210000)), "Направление": "Поступление" if is_income else "Списание",
                "Контрагент": "Разовая операция", "ИНН контрагента": "",
                "Назначение платежа": "Разовый платёж",
            })
    frame = pd.DataFrame(transactions).sort_values(["Дата операции", "Контрагент"]).reset_index(drop=True)
    signed = np.where(frame["Направление"].eq("Поступление"), frame["Сумма"], -frame["Сумма"])
    daily_net = pd.Series(signed, index=frame["Дата операции"]).groupby(level=0).sum()
    balance = 12_800_000.0
    close_by_date: dict[pd.Timestamp, float] = {}
    for date in pd.date_range(start, end, freq="D"):
        balance += float(daily_net.get(date, 0.0))
        close_by_date[date] = balance
    frame["Остаток на конец дня"] = frame["Дата операции"].map(close_by_date).round(2)
    frame["Счёт"] = "Расчётный счёт"
    events = pd.DataFrame([
        {"date": end + pd.Timedelta(days=8), "amount": 210000, "direction": "поступление", "category": "Выручка и поступления от клиентов", "event_type": "ожидаемое поступление по договору", "status": "подтверждено", "source": "демо: договор", "description": "Оплата по договору от клиента", "account": "Расчётный счёт"},
        {"date": end + pd.Timedelta(days=12), "amount": 185000, "direction": "списание", "category": "Закупки и поставщики", "event_type": "счёт поставщика", "status": "подтверждено", "source": "демо: счёт поставщика", "description": "Счёт поставщика за материалы", "account": "Расчётный счёт"},
        {"date": end + pd.Timedelta(days=35), "amount": 150000, "direction": "списание", "category": "Налоги и обязательные платежи", "event_type": "налоговый платёж (ввод пользователя)", "status": "ожидается", "source": "демо: ручной ввод", "description": "Условный налоговый платёж; сумма для демонстрации", "account": "Расчётный счёт"},
    ])
    return frame, events


def ensure_demo_files() -> tuple[Path, Path]:
    """Create checked-in style CSV fixtures when they are missing."""
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    statement_path = DEMO_DIR / "demo_statement.csv"
    events_path = DEMO_DIR / "demo_future_events.csv"
    if not statement_path.exists() or not events_path.exists():
        statement, events = generate_demo_data()
        statement.to_csv(statement_path, index=False, encoding="utf-8-sig")
        events.to_csv(events_path, index=False, encoding="utf-8-sig")
    return statement_path, events_path
