"""
Тесты шага 2: контент, авторизация, квесты, XP-формулы.
"""

import pytest
from fastapi.testclient import TestClient

from app.game.xp_engine import (
    add_xp,
    level_from_xp,
    level_progress_pct,
    level_title,
    xp_for_level,
    xp_to_next_level,
)
from app.main import app

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Логинимся один раз, возвращаем заголовок для остальных тестов."""
    resp = client.post("/api/auth/login", json={"username": "test_parker"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# XP Engine
# ---------------------------------------------------------------------------

class TestXpEngine:
    def test_level_1_at_zero(self):
        assert level_from_xp(0) == 1

    def test_level_2_at_50(self):
        assert level_from_xp(50) == 2

    def test_level_3_at_200(self):
        assert level_from_xp(200) == 3

    def test_level_5_at_800(self):
        assert level_from_xp(800) == 5

    def test_xp_for_level_1_is_zero(self):
        assert xp_for_level(1) == 0

    def test_xp_for_level_2_is_50(self):
        assert xp_for_level(2) == 50

    def test_xp_to_next_level(self):
        # На 0 XP до уровня 2 нужно 50 XP
        assert xp_to_next_level(0) == 50

    def test_level_progress_pct_at_start(self):
        pct = level_progress_pct(0)
        assert 0.0 <= pct <= 1.0

    def test_add_xp_no_levelup(self):
        new_xp, new_level, leveled_up = add_xp(0, 30)
        assert new_xp == 30
        assert new_level == 1
        assert not leveled_up

    def test_add_xp_with_levelup(self):
        new_xp, new_level, leveled_up = add_xp(0, 50)
        assert new_xp == 50
        assert new_level == 2
        assert leveled_up

    def test_level_title_exists(self):
        assert level_title(1) == "Стажёр"
        assert level_title(5) == "Молодой специалист"


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

class TestSeeding:
    def test_quests_seeded(self, client):
        """После старта в БД должно быть 7 квестов."""
        from app.db.database import SessionLocal
        from app.db.models import Quest
        db = SessionLocal()
        count = db.query(Quest).count()
        db.close()
        assert count == 7

    def test_achievements_seeded(self, client):
        """После старта в БД должно быть 5 ачивок."""
        from app.db.database import SessionLocal
        from app.db.models import Achievement
        db = SessionLocal()
        count = db.query(Achievement).count()
        db.close()
        assert count == 5

    def test_first_quest_has_no_prerequisite(self, client):
        from app.db.database import SessionLocal
        from app.db.models import Quest
        db = SessionLocal()
        q = db.query(Quest).filter(Quest.slug == "first_steps").first()
        db.close()
        assert q is not None
        assert q.prerequisite_slug is None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_login_creates_user(self, client):
        resp = client.post("/api/auth/login", json={"username": "new_user_xyz"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "new_user_xyz"
        assert data["user"]["level"] == 1
        assert data["user"]["total_xp"] == 0

    def test_login_same_user_twice(self, client):
        """Повторный логин возвращает того же пользователя."""
        resp1 = client.post("/api/auth/login", json={"username": "same_user_test"})
        resp2 = client.post("/api/auth/login", json={"username": "same_user_test"})
        assert resp1.json()["user"]["id"] == resp2.json()["user"]["id"]

    def test_login_invalid_username(self, client):
        """Никнейм с запрещёнными символами → 422."""
        resp = client.post("/api/auth/login", json={"username": "bad user!"})
        assert resp.status_code == 422

    def test_unauthorized_without_token(self, client):
        resp = client.get("/api/users/me")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestUsers:
    def test_get_my_profile(self, client, auth_headers):
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test_parker"
        assert "level_title" in data
        assert "xp_to_next_level" in data
        assert "level_progress_pct" in data

    def test_leaderboard(self, client, auth_headers):
        resp = client.get("/api/users/leaderboard", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------

class TestQuests:
    def test_list_quests(self, client, auth_headers):
        resp = client.get("/api/quests", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        slugs = [q["slug"] for q in data["quests"]]
        assert "first_steps" in slugs
        assert "boss_inspection" in slugs

    def test_first_quest_is_available(self, client, auth_headers):
        resp = client.get("/api/quests/first_steps", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "available"

    def test_locked_quest_cannot_start(self, client, auth_headers):
        """boss_inspection заблокирован — нельзя начать."""
        resp = client.post("/api/quests/boss_inspection/start", headers=auth_headers)
        assert resp.status_code == 403

    def test_start_and_complete_quest(self, client, auth_headers):
        """Начинаем first_steps, завершаем, проверяем XP."""
        # Старт
        resp = client.post("/api/quests/first_steps/start", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # Завершение
        resp = client.post("/api/quests/first_steps/complete", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["xp_gained"] == 50
        assert data["new_total_xp"] == 50

    def test_next_quest_unlocked_after_completion(self, client, auth_headers):
        """После first_steps должен разблокироваться safety_first."""
        resp = client.get("/api/quests/safety_first", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "available"

    def test_cannot_complete_not_active_quest(self, client, auth_headers):
        """Нельзя завершить квест который не начат."""
        resp = client.post("/api/quests/emergency_stop/complete", headers=auth_headers)
        assert resp.status_code == 400
