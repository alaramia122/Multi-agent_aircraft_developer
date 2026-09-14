from pathlib import Path

from engineering_gateway.domain.models import ElementKind, RelationType
from engineering_gateway.infrastructure.profile_loader import load_standard_profile


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles" / "arp4754a" / "1.0" / "profile.json"


def test_load_arp4754a_vertical_slice_profile() -> None:
    profile = load_standard_profile(PROFILE)

    assert (profile.id, profile.version) == ("arp4754a", "1.0")
    assert {item.id for item in profile.element_types} == {
        "system_requirement",
        "system_architecture",
        "verification_activity",
    }
    assert profile.element_types[0].kind is ElementKind.REQUIREMENT
    assert profile.traceability[0].relation_type is RelationType.ALLOCATED_TO
    assert profile.verification[0].required_relation_type is RelationType.VERIFIED_BY
