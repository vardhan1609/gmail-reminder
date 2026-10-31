from pathlib import Path

from fastapi.testclient import TestClient

import app.database.session as session_module
from app.config import settings
from app.models.db_models import AccountModel, GmailConnectionModel, SyncStateModel, UserModel


def _register_user(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "ValidPassword123!",
            "full_name": "Disconnect Test",
            "terms_accepted": True,
        },
    )
    assert response.status_code in (200, 201), response.text

    db = session_module.SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.email == email).one()
        return user.id
    finally:
        db.close()


def test_gmail_disconnect_removes_only_owned_connection_and_legacy_rows(client, tmp_path):
    owner_id = _register_user(client, "disconnect-owner@example.com")
    other_id = _register_user(client, "disconnect-other@example.com")

    # Authenticate as the owner after creating both users (the second login
    # otherwise replaces the shared TestClient cookie).
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "disconnect-owner@example.com", "password": "ValidPassword123!"},
    )
    assert login.status_code == 200, login.text

    owner_token = tmp_path / "owner-token.json"
    other_token = tmp_path / "other-token.json"
    owner_token.write_text("owner-token")
    other_token.write_text("other-token")

    db = session_module.SessionLocal()
    try:
        owner_connection = GmailConnectionModel(
            user_id=owner_id,
            email="owner@gmail.com",
            token_path=str(owner_token),
            active=True,
        )
        other_connection = GmailConnectionModel(
            user_id=other_id,
            email="other@gmail.com",
            token_path=str(other_token),
            active=True,
        )
        db.add_all([owner_connection, other_connection])
        db.flush()
        owner_connection_id = owner_connection.id
        other_connection_id = other_connection.id
        db.add_all([
            AccountModel(
                user_id=owner_id,
                email="owner@gmail.com",
                token_path=str(owner_token),
                active=True,
            ),
            AccountModel(
                user_id=other_id,
                email="other@gmail.com",
                token_path=str(other_token),
                active=True,
            ),
            SyncStateModel(
                user_id=owner_id,
                account_identifier="owner@gmail.com",
                last_sync_status="idle",
            ),
            SyncStateModel(
                user_id=other_id,
                account_identifier="other@gmail.com",
                last_sync_status="idle",
            ),
        ])
        db.commit()
    finally:
        db.close()

    # A caller must not be able to disconnect another tenant's mailbox.
    foreign_response = client.delete(f"/api/v1/integrations/gmail/{other_connection_id}")
    assert foreign_response.status_code == 200

    db = session_module.SessionLocal()
    try:
        assert db.query(GmailConnectionModel).filter_by(id=other_connection_id).one_or_none()
        assert db.query(AccountModel).filter_by(email="other@gmail.com").one_or_none()
        assert db.query(SyncStateModel).filter_by(account_identifier="other@gmail.com").one_or_none()
    finally:
        db.close()
    assert other_token.exists()

    response = client.delete(f"/api/v1/integrations/gmail/{owner_connection_id}")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Gmail account disconnected successfully."

    db = session_module.SessionLocal()
    try:
        assert db.query(GmailConnectionModel).filter_by(id=owner_connection_id).one_or_none() is None
        assert db.query(AccountModel).filter_by(email="owner@gmail.com").one_or_none() is None
        assert db.query(SyncStateModel).filter_by(account_identifier="owner@gmail.com").one_or_none() is None
        assert db.query(GmailConnectionModel).filter_by(id=other_connection_id).one_or_none()
    finally:
        db.close()

    assert not owner_token.exists()
    assert other_token.exists()
