import io
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_migration_generates_postgres_sql():
    output = io.StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE monitors" in sql and "CREATE TABLE check_results" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "ON DELETE CASCADE" in sql
    assert "ix_check_results_time" in sql
    assert "target_url VARCHAR(2048) NOT NULL" in sql
