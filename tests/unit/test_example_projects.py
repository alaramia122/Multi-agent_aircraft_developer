"""Each teaching project exercises a complete deterministic profile trace chain."""

from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from engineering_gateway.api.example_projects import example_projects
from engineering_gateway.api.human_review import create_human_review_app
from engineering_gateway.application.validation import DeterministicValidationEngine
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.infrastructure.profile_loader import load_standard_profile


PROFILES = Path(__file__).resolve().parents[2] / "profiles"


def test_three_distinct_example_projects_validate_full_profile_graphs() -> None:
    examples = example_projects()
    assert len(examples) == 3
    assert len({example["id"] for example in examples}) == 3
    for example in examples:
        profile = load_standard_profile(PROFILES / example["profile"]["id"] / example["profile"]["version"] / "profile.json")
        by_key = {
            item["key"]: EngineeringElement(
                id=uuid5(NAMESPACE_URL, f"demo:{example['id']}:{item['key']}"),
                kind=item["kind"],
                type_id=item["type_id"],
                name=item["name"],
                external_system="example",
                external_id=f"{example['id']}/{item['key']}",
            )
            for item in example["elements"]
        }
        assert len(by_key) == len(example["elements"])
        assert all(item["detail"] for item in example["elements"])
        relations = [
            EngineeringRelation(
                source_id=by_key[source].id,
                relation_type=relation,
                target_id=by_key[target].id,
            )
            for source, relation, target in example["relations"]
        ]
        lifecycle_types = {lifecycle.element_type_id for lifecycle in profile.lifecycles}
        result = DeterministicValidationEngine().validate(
            list(by_key.values()),
            relations,
            profile,
            lifecycle_states={item.id: "draft" for item in by_key.values() if item.type_id in lifecycle_types},
        )
        assert result.valid, (example["id"], result.issues)
        assert len(relations) >= 10


def test_catalog_returns_independent_data() -> None:
    first = example_projects()
    first[0]["elements"].clear()
    assert len(example_projects()[0]["elements"]) == 9


def test_public_catalog_is_visible_without_a_human_token() -> None:
    verifier = SimpleNamespace(issuer="https://idp.example/realms/engineering", client_ids={"human-ui"})
    client = TestClient(create_human_review_app(lambda: None, verifier))
    response = client.get("/examples")
    assert response.status_code == 200
    assert response.json()["kind"] == "read_only_demonstration"
    assert {item["id"] for item in response.json()["examples"]} == {
        "course-hold", "battery-monitor", "telemetry-integrity",
    }
