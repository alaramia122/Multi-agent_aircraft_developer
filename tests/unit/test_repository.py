from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.infrastructure.db import Base
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository


@pytest.mark.asyncio
async def test_repository_round_trip() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repository = SqlAlchemyEngineeringRepository(session)
        first = EngineeringElement(
            kind=ElementKind.REQUIREMENT,
            type_id="system-requirement",
            name="Requirement",
            external_system="strictdoc",
            external_id="REQ-001",
        )
        second = EngineeringElement(
            kind=ElementKind.VERIFICATION,
            type_id="test-case",
            name="Test",
            external_system="strictdoc",
            external_id="TC-001",
        )
        await repository.save(first)
        await repository.save(second)
        relation = EngineeringRelation(
            source_id=first.id,
            relation_type=RelationType.VERIFIED_BY,
            target_id=second.id,
        )
        await repository.add_relation(relation)
        await session.commit()

        loaded = await repository.get(first.id)
        relations = await repository.get_relations(first.id)

    await engine.dispose()

    assert loaded == first
    assert relations == [relation]


@pytest.mark.asyncio
async def test_relation_requires_existing_endpoints() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repository = SqlAlchemyEngineeringRepository(session)
        with pytest.raises(ValueError, match="Both relation endpoints"):
            await repository.add_relation(
                EngineeringRelation(
                    source_id=uuid4(),
                    relation_type=RelationType.DEPENDS_ON,
                    target_id=uuid4(),
                )
            )

    await engine.dispose()
