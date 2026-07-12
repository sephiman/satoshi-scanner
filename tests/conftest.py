
import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(scope="session")
def session_monkeypatch():
    mp = MonkeyPatch()
    yield mp
    mp.undo()


def _docker_available() -> bool:
    try:
        import docker  # noqa: F401
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_container():
    if not _docker_available():
        pytest.skip("Docker not available; skipping testcontainers-backed tests")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_env(postgres_container, session_monkeypatch):
    session_monkeypatch.setenv("POSTGRES_HOST", postgres_container.get_container_host_ip())
    session_monkeypatch.setenv(
        "POSTGRES_PORT", str(postgres_container.get_exposed_port(5432))
    )
    session_monkeypatch.setenv("POSTGRES_USER", postgres_container.username)
    session_monkeypatch.setenv("POSTGRES_PASSWORD", postgres_container.password)
    session_monkeypatch.setenv("POSTGRES_DB", postgres_container.dbname)
    yield


@pytest.fixture
def db_conn(pg_env):
    import db as db_module

    conn = db_module.get_conn()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS funded_addresses")
    conn.commit()
    yield conn
    conn.close()
