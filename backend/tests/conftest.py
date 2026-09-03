import os
import uuid
from collections.abc import Generator

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-thirty-two-characters")
os.environ.setdefault("APP_ENV", "test")
os.environ["CLOUDFLARE_QUICK_TUNNEL_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import Base, Company, User, UserRole
from app.db.session import get_db
from app.main import app


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def tenants(db: Session) -> dict:
    company_a = Company(name="Tenant A")
    company_b = Company(name="Tenant B")
    db.add_all([company_a, company_b])
    db.flush()
    admin_a = User(
        company_id=company_a.id,
        name="Admin A",
        email="admin-a@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=UserRole.ADMIN,
    )
    admin_b = User(
        company_id=company_b.id,
        name="Admin B",
        email="admin-b@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=UserRole.ADMIN,
    )
    super_admin = User(
        company_id=company_a.id,
        name="Super Admin",
        email="super@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=UserRole.SUPER_ADMIN,
    )
    staff_a = User(
        company_id=company_a.id,
        name="Staff A",
        email="staff-a@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=UserRole.STAFF,
    )
    db.add_all([admin_a, admin_b, super_admin, staff_a])
    db.commit()

    def headers(user: User, company_id: uuid.UUID | None = None) -> dict[str, str]:
        token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            company_id=str(user.company_id) if user.company_id else None,
        )
        result = {"Authorization": f"Bearer {token}"}
        if company_id:
            result["X-Company-ID"] = str(company_id)
        return result

    return {
        "company_a": company_a,
        "company_b": company_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "super_admin": super_admin,
        "staff_a": staff_a,
        "headers_a": headers(admin_a),
        "headers_b": headers(admin_b),
        "staff_headers_a": headers(staff_a),
        "super_headers_b": headers(super_admin, company_b.id),
    }
