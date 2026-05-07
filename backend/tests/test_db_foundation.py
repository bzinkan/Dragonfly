from app.db import models  # noqa: F401
from app.db.base import Base


def test_postgres_foundation_tables_are_registered() -> None:
    table_names = set(Base.metadata.tables)

    assert {
        "users",
        "groups",
        "memberships",
        "photos",
        "observations",
        "dex_entries",
        "expedition_progress",
        "review_queue",
        "ingest_runs",
        "job_state",
        "species_cache",
        "geo_cache",
        "rarity_cache",
        "expedition_content",
    }.issubset(table_names)


def test_first_find_and_ingest_idempotency_constraints_exist() -> None:
    dex_constraints = {
        constraint.name for constraint in Base.metadata.tables["dex_entries"].constraints
    }
    ingest_constraints = {
        constraint.name for constraint in Base.metadata.tables["ingest_runs"].constraints
    }

    assert "uq_dex_entries_user_taxon" in dex_constraints
    assert "uq_ingest_runs_source_run" in ingest_constraints
