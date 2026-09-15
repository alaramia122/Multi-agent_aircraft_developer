import re  # noqa: I001
from pathlib import Path


MIGRATIONS = Path(__file__).parents[2] / "migrations"
VERSIONED_MIGRATION = re.compile(r"^(\d{4})_.+\.sql$")


def test_numbered_migrations_have_unique_order_and_no_duplicate_versions() -> None:
    files = sorted(
        path.name
        for path in MIGRATIONS.iterdir()
        if path.is_file() and VERSIONED_MIGRATION.match(path.name)
    )
    versions = [int(VERSIONED_MIGRATION.match(name).group(1)) for name in files]

    assert versions == sorted(set(versions)), "migration version numbers must be unique"
