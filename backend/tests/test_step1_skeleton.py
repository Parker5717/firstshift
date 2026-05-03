"""
Smoke-тесты шага 1: убеждаемся что приложение запускается, БД инициализируется,
все таблицы созданы, /health отвечает 200.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.database import engine
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """GET /health возвращает 200 и структуру со статусом."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


def test_root_endpoint(client):
    """GET / возвращает HTML login-страницу (шаг 3+)."""
    response = client.get("/")
    assert response.status_code == 200
    # Теперь / отдаёт index.html, а не JSON
    assert "CASPER" in response.text or response.status_code == 200


def test_all_tables_created(client):
    """После запуска lifespan все таблицы должны существовать в БД."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    expected = {
        "users",
        "quests",
        "user_quest_progress",
        "achievements",
        "user_achievements",
        "scan_events",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"


def test_openapi_schema_loads(client):
    """Swagger /docs доступен — значит, все роутеры подключились без ошибок."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CASPER AR Assistant"
