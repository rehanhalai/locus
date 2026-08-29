import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 - ensure all tables are registered
from app.db import session as db_session
from app.db.session import Base, get_db
from app.main import app
from app.modules.acquisition import service as acq_service
from app.modules.carver import service as carver_service
from app.modules.header_parser import service as hdr_service
from app.modules.identification import service as ident_service

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Creates all tables in the in-memory test database and patches SessionLocal
    so background workers write to the test database instead of production disk.
    """
    Base.metadata.create_all(bind=test_engine)
    db_session.SessionLocal = TestingSessionLocal
    acq_service.SessionLocal = TestingSessionLocal
    ident_service.SessionLocal = TestingSessionLocal
    hdr_service.SessionLocal = TestingSessionLocal
    carver_service.db_session.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db

    yield

    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client():
    """
    FastAPI test client fixture running against the isolated in-memory test DB.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """
    Yields a direct SQLAlchemy Session to the isolated test database for direct assertions.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
