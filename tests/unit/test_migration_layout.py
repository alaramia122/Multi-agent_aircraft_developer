import re  # noqa: I001
from pathlib import Path


MIGRATIONS = Path(__file__).parents[2] / "migrations"
BOOTSTRAP_MIGRATIONS = MIGRATIONS / "versions"
VERSIONED_MIGRATION = re.compile(r"^(\d{4})_.+\.sql$")


def _migration_versions(directory: Path) -> list[int]:
    files = sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file() and VERSIONED_MIGRATION.match(path.name)
    )
    return [int(VERSIONED_MIGRATION.match(name).group(1)) for name in files]


def test_numbered_migrations_have_unique_order_and_no_duplicate_versions() -> None:
    versions = _migration_versions(MIGRATIONS)

    assert versions == sorted(set(versions)), "migration version numbers must be unique"


def test_active_migrations_have_explicit_contiguous_sequence_except_historical_gap() -> None:
    assert _migration_versions(MIGRATIONS) == [3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14]


def test_bootstrap_migrations_are_exactly_the_historical_v1_and_v2() -> None:
    assert _migration_versions(BOOTSTRAP_MIGRATIONS) == [1, 2]
