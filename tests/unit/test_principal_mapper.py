from __future__ import annotations

import pytest

from engineering_gateway.api.principal_mapper import ClaimMapping, TrustedClaimsActorMapper
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


def test_trusted_claims_are_mapped_to_actor() -> None:
    mapper = TrustedClaimsActorMapper()

    actor = mapper.map_actor(
        {
            "sub": "alice@example.test",
            "actor_type": "human",
            "authorization_level": "L3_APPROVE",
        }
    )

    assert actor.actor_id == "alice@example.test"
    assert actor.actor_type is ActorType.HUMAN
    assert actor.authorization_level is AuthorizationLevel.L3_APPROVE


def test_custom_claim_names_are_supported() -> None:
    mapper = TrustedClaimsActorMapper(
        ClaimMapping(
            actor_id_claim="uid",
            actor_type_claim="type",
            authorization_level_claim="role",
        )
    )

    actor = mapper.map_actor(
        {"uid": "service-1", "type": "service", "role": "L2_MODIFY_WORKSPACE"}
    )

    assert actor.actor_id == "service-1"
    assert actor.actor_type is ActorType.SERVICE
    assert actor.authorization_level is AuthorizationLevel.L2_MODIFY_WORKSPACE


@pytest.mark.parametrize(
    "claims, message",
    [
        ({"actor_type": "human", "authorization_level": "L0_READ"}, "sub"),
        ({"sub": "alice", "authorization_level": "L0_READ"}, "actor_type"),
        ({"sub": "alice", "actor_type": "human"}, "authorization_level"),
    ],
)
def test_missing_claims_are_rejected(claims: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TrustedClaimsActorMapper().map_actor(claims)


def test_invalid_enum_claim_is_rejected() -> None:
    with pytest.raises(ValueError, match="authorization_level"):
        TrustedClaimsActorMapper().map_actor(
            {
                "sub": "alice",
                "actor_type": "human",
                "authorization_level": "L9_ADMIN",
            }
        )


def test_actor_id_is_normalized() -> None:
    actor = TrustedClaimsActorMapper().map_actor(
        {
            "sub": "  alice  ",
            "actor_type": "human",
            "authorization_level": "L0_READ",
        }
    )

    assert actor.actor_id == "alice"
