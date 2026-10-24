import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.storage import SQLiteStore
from app.main import app
from app.services.data_loader import Dataset


def _dataset():
    companies = pd.DataFrame([{
        "company_id": "C001", "name": "Компания Один", "inn": "000100", "legal_form": "ООО",
        "industry": "Торговля", "first_operation_date": "2025-01-01", "last_operation_date": "2025-01-02",
    }, {
        "company_id": "C002", "name": "Компания Два", "inn": "000200", "legal_form": "ИП",
        "industry": "Услуги", "first_operation_date": "2025-01-01", "last_operation_date": "2025-01-02",
    }])
    rows = []
    for company_id, balance in (("C001", 1100), ("C002", 900)):
        rows.append({
            "company_id": company_id, "operation_id": f"{company_id}-1",
            "date": pd.Timestamp("2025-01-01"), "operation_date": pd.Timestamp("2025-01-01"),
            "amount": 100, "signed_amount": 100, "direction": "поступление",
            "counterparty_inn": "000001", "counterparty_name": "Покупатель",
            "payment_purpose": "Оплата от клиента", "balance_eod": balance,
            "balance": balance, "counterparty": "Покупатель", "inn": "000001",
            "purpose": "Оплата от клиента", "account": company_id,
        })
    return Dataset(companies, pd.DataFrame(rows), "ready", "loaded", [])


def test_api_company_isolation_pagination_and_saved_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: _dataset())
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "test.sqlite"))
    app.state.dataset = _dataset()
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "test.sqlite")
    with TestClient(app) as client:
        assert client.get("/api/health").json()["companies"] == 2
        listing = client.get("/api/companies?page=1&page_size=1").json()
        assert listing["total"] == 2
        assert len(listing["items"]) == 1
        rows = client.get("/api/companies/C001/operations?page_size=1").json()
        assert rows["total"] == 1
        assert rows["items"][0]["company_id"] == "C001"
        operation_id = rows["items"][0]["operation_id"]
        changed = client.patch(f"/api/companies/C001/operations/{operation_id}/category", json={"category": "Аренда"})
        assert changed.status_code == 200
        assert client.get("/api/companies/C001/operations").json()["items"][0]["category"] == "Аренда"
        assert client.get("/api/companies/C002/operations").json()["items"][0]["category"] != "Аренда"


def test_operations_api_returns_categories_and_filters_them(tmp_path, monkeypatch):
    dataset = _dataset()
    unknown = dataset.operations.iloc[0].copy()
    unknown["operation_id"] = "C001-2"
    unknown["date"] = pd.Timestamp("2025-01-02")
    unknown["operation_date"] = pd.Timestamp("2025-01-02")
    unknown["amount"] = -250
    unknown["signed_amount"] = -250
    unknown["direction"] = "списание"
    unknown["counterparty_name"] = "Неизвестный контрагент"
    unknown["counterparty"] = "Неизвестный контрагент"
    unknown["payment_purpose"] = "Неизвестная операция"
    unknown["purpose"] = "Неизвестная операция"
    dataset.operations = pd.concat([dataset.operations, unknown.to_frame().T], ignore_index=True)
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: dataset)
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "auto-categories.sqlite"))
    app.state.dataset = dataset
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "auto-categories.sqlite")

    with TestClient(app) as client:
        response = client.get("/api/companies/C001/operations?page_size=10")
        filtered = client.get("/api/companies/C001/operations?category=Прочие%20расходы")

    items = response.json()["items"]
    assert response.status_code == 200
    assert all(item["category"] for item in items)
    assert items[0]["category"] == "Прочие расходы"
    assert items[1]["category"] == "Выручка и поступления от клиентов"
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["operation_id"] == "C001-2"


def test_operations_api_survives_a_classification_error(tmp_path, monkeypatch):
    import app.services.categorization as categorization_service

    monkeypatch.setattr(main_module, "load_dataset", lambda _path: _dataset())
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "classification-error.sqlite"))
    monkeypatch.setattr(
        categorization_service, "categorize_rule",
        lambda _operation: (_ for _ in ()).throw(ValueError("invalid payment data")),
    )
    app.state.dataset = _dataset()
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "classification-error.sqlite")

    with TestClient(app) as client:
        response = client.get("/api/companies/C001/operations")

    assert response.status_code == 200
    assert response.json()["items"][0]["category"] == "Прочие поступления"


def test_api_event_create_edit_cancel_are_company_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: _dataset())
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "events.sqlite"))
    app.state.dataset = _dataset()
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "events.sqlite")
    payload = {
        "date": "2025-02-01", "amount": 1234, "direction": "списание",
        "category": "Аренда", "event_type": "счёт поставщика",
        "description": "Оплата аренды", "source": "тест", "status": "Ожидается",
    }
    with TestClient(app) as client:
        created = client.post("/api/companies/C001/events", json=payload)
        assert created.status_code == 201
        event_id = created.json()["id"]
        assert client.get("/api/companies/C002/events").json()["items"] == []
        updated = client.patch(f"/api/companies/C001/events/{event_id}", json={"status": "Подтверждено"})
        assert updated.json()["status"] == "Подтверждено"
        cancelled = client.delete(f"/api/companies/C001/events/{event_id}")
        assert cancelled.json()["status"] == "Отменено"


def test_api_imports_event_description_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: _dataset())
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "imported-events.sqlite"))
    app.state.dataset = _dataset()
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "imported-events.sqlite")
    csv_data = "дата;сумма;направление;описание\n01.02.2025;1234;списание;Оплата аренды\n".encode("utf-8")

    with TestClient(app) as client:
        response = client.post(
            "/api/companies/C001/events/import",
            files={"file": ("events.csv", csv_data, "text/csv")},
        )

    assert response.status_code == 200
    imported = response.json()["items"][0]
    assert imported["description"] == "Оплата аренды"
    assert imported["amount"] == 1234


def test_model_evaluation_returns_one_row_per_date_with_method_columns(tmp_path, monkeypatch):
    dataset = _dataset()
    rows = []
    balance = 10000
    for day in pd.date_range("2025-01-01", periods=140):
        signed_amount = 100 if day.day % 2 else -80
        balance += signed_amount
        rows.append({
            "company_id": "C001", "operation_id": day.strftime("C001-%Y%m%d"),
            "date": day, "operation_date": day, "amount": abs(signed_amount),
            "signed_amount": signed_amount,
            "direction": "поступление" if signed_amount > 0 else "списание",
            "payment_purpose": "Оплата от клиента", "balance_eod": balance,
            "balance": balance, "account": "C001", "purpose": "Оплата от клиента",
            "counterparty": "Покупатель", "inn": "000001",
        })
    dataset.operations = pd.DataFrame(rows)
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: dataset)
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "model-evaluation.sqlite"))
    app.state.dataset = dataset
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "model-evaluation.sqlite")

    with TestClient(app) as client:
        response = client.get("/api/companies/C001/model-evaluation")
        forecast = client.get("/api/companies/C001/forecast?horizon=30")
        risk = client.get("/api/companies/C001/risks?horizon=30")
        summary = client.get("/api/companies/C001/summary?horizon=30")
        invalid_horizon = client.get("/api/companies/C001/forecast?horizon=31")

    assert response.status_code == 200
    assert forecast.status_code == 200
    assert len(forecast.json()["items"]) == 30
    assert risk.status_code == 200
    assert risk.json()["horizon_days"] == 30
    assert summary.status_code == 200
    assert invalid_horizon.status_code == 422
    payload = response.json()
    assert payload["metrics"]
    assert {row["method"] for row in payload["metrics"]} == {"baseline", "ML"}
    assert payload["backtest"]
    assert {"date", "actual_net", "baseline", "ML"} <= payload["backtest"][0].keys()


def test_api_reports_missing_company_and_rejects_invalid_category(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "load_dataset", lambda _path: _dataset())
    monkeypatch.setattr(main_module, "SQLiteStore", lambda: SQLiteStore(tmp_path / "errors.sqlite"))
    app.state.dataset = _dataset()
    app.state.data_directory = tmp_path
    app.state.store = SQLiteStore(tmp_path / "errors.sqlite")
    with TestClient(app) as client:
        assert client.get("/api/companies/C999/operations").status_code == 404
        assert client.patch("/api/companies/C001/operations/C001-1/category", json={"category": "invalid"}).status_code == 422
