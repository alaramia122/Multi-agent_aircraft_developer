"""Gateway-owned SQLAlchemy persistence models.

Only canonical references, graph edges and Gateway metadata are persisted here;
external engineering-system payloads are not copied into this schema.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from engineering_gateway.infrastructure.db import Base


class EngineeringElementRecord(Base):
    __tablename__ = "engineering_elements"
    __table_args__ = (
        UniqueConstraint("external_system", "external_id", name="uq_element_external_identity"),
        Index("ix_engineering_elements_kind", "kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    type_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    external_system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(2048))

    outgoing: Mapped[list["EngineeringRelationRecord"]] = relationship(
        foreign_keys="EngineeringRelationRecord.source_id", back_populates="source"
    )
    incoming: Mapped[list["EngineeringRelationRecord"]] = relationship(
        foreign_keys="EngineeringRelationRecord.target_id", back_populates="target"
    )


class EngineeringRelationRecord(Base):
    __tablename__ = "engineering_relations"
    __table_args__ = (
        UniqueConstraint("source_id", "relation_type", "target_id", name="uq_engineering_relation"),
        Index("ix_relations_source", "source_id"),
        Index("ix_relations_target", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("engineering_elements.id", ondelete="RESTRICT"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("engineering_elements.id", ondelete="RESTRICT"), nullable=False
    )

    source: Mapped[EngineeringElementRecord] = relationship(
        foreign_keys=[source_id], back_populates="outgoing"
    )
    target: Mapped[EngineeringElementRecord] = relationship(
        foreign_keys=[target_id], back_populates="incoming"
    )
