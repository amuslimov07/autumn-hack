import pandas as pd

from app.services.data_loader import load_dataset, validate_daily_balances


def test_loads_utf8_bom_semicolon_inns_and_signed_operations(tmp_path):
    (tmp_path / "companies.csv").write_text(
        "\ufeffcompany_id;name;inn;legal_form;industry\nC001;Тест;000123456789;ООО;Торговля\n",
        encoding="utf-8",
    )
    operations_dir = tmp_path / "statements"
    operations_dir.mkdir()
    (operations_dir / "C001.csv").write_text(
        "\ufeffoperation_id;operation_date;amount;direction;counterparty_inn;counterparty_name;payment_purpose;balance_eod\n"
        "O1;2025-01-02;1000;Поступление;0000012345;Клиент;Оплата;5500\n"
        "O2;2025-01-02;500;Списание;0000098765;Поставщик;Закупка;5500\n",
        encoding="utf-8",
    )
    dataset = load_dataset(tmp_path)
    assert dataset.status == "ready"
    assert dataset.companies.iloc[0]["inn"] == "000123456789"
    assert dataset.operations.iloc[0]["counterparty_inn"] == "0000012345"
    assert sorted(dataset.operations["signed_amount"].tolist()) == [-500, 1000]
    balances = validate_daily_balances(dataset.operations)
    assert balances.iloc[0]["opening_balance"] == 5000
    assert balances.iloc[0]["operations"] == 2


def test_combined_source_takes_precedence_over_duplicate_individual_files(tmp_path):
    (tmp_path / "companies.csv").write_text("company_id;name\nC001;Test\n", encoding="utf-8-sig")
    (tmp_path / "all_operations.csv").write_text(
        "company_id;operation_id;operation_date;amount;direction;counterparty_inn;counterparty_name;payment_purpose;balance_eod\n"
        "C001;O1;2025-01-01;10;Поступление;001;Buyer;Sale;20\n",
        encoding="utf-8-sig",
    )
    statements = tmp_path / "statements"
    statements.mkdir()
    (statements / "C001.csv").write_text(
        "operation_id;operation_date;amount;direction;counterparty_inn;counterparty_name;payment_purpose;balance_eod\n"
        "O1;2025-01-01;10;Поступление;001;Buyer;Sale;20\n",
        encoding="utf-8-sig",
    )
    dataset = load_dataset(tmp_path)
    assert len(dataset.operations) == 1
    assert dataset.operations.iloc[0]["company_id"] == "C001"


def test_missing_dataset_returns_a_diagnostic_instead_of_crashing(tmp_path):
    result = load_dataset(tmp_path)
    assert result.status == "missing"
    assert "companies.csv" in result.message
    assert result.operations.empty


def test_daily_balance_validation_does_not_report_gaps_as_zero_flow_days():
    rows = pd.DataFrame({
        "company_id": ["A", "A"], "date": pd.to_datetime(["2025-01-01", "2025-01-04"]),
        "signed_amount": [100, -20], "balance_eod": [1100, 1080], "operation_id": ["1", "2"],
    })
    result = validate_daily_balances(rows)
    assert len(result) == 2
    assert result["date"].tolist() == list(pd.to_datetime(["2025-01-01", "2025-01-04"]))
    assert result["balance_consistent"].all()
