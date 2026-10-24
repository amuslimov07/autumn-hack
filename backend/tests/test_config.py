import logging

from app.core.config import _resolve_data_dir


def test_relative_dataset_path_resolves_from_backend_when_started_at_project_root(tmp_path, caplog):
    project_dir = tmp_path / "project"
    backend_dir = project_dir / "backend"
    dataset_dir = project_dir / "data" / "dataset"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "companies.csv").touch()

    with caplog.at_level(logging.WARNING):
        resolved = _resolve_data_dir(
            "..\\data\\dataset",
            project_dir=project_dir,
            backend_dir=backend_dir,
            cwd=project_dir,
        )

    assert resolved == dataset_dir.resolve()
    assert "Resolved relative CASHFLOW_DATA_DIR" in caplog.text


def test_relative_dataset_path_uses_working_directory_when_dataset_exists(tmp_path):
    working_dir = tmp_path / "working"
    dataset_dir = working_dir / "custom-dataset"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "companies.csv").touch()

    resolved = _resolve_data_dir(
        "custom-dataset",
        project_dir=tmp_path / "project",
        backend_dir=tmp_path / "project" / "backend",
        cwd=working_dir,
    )

    assert resolved == dataset_dir.resolve()
