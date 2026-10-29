"""Canonical places, events, and approved memory entity links."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, JSON, String, UniqueConstraint

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import DateAccuracy


class Place(Base):
    __tablename__ = "places"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    description = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    date_accuracy = Column(String, default=DateAccuracy.APPROXIMATE.value)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemoryPersonLink(Base):
    __tablename__ = "memory_people"
    __table_args__ = (UniqueConstraint("memory_id", "person_id", name="uq_memory_person"),)

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)
    person_id = Column(String, ForeignKey("people.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class MemoryPlaceLink(Base):
    __tablename__ = "memory_places"
    __table_args__ = (UniqueConstraint("memory_id", "place_id", name="uq_memory_place"),)

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)
    place_id = Column(String, ForeignKey("places.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class MemoryEventLink(Base):
    __tablename__ = "memory_events"
    __table_args__ = (UniqueConstraint("memory_id", "event_id", name="uq_memory_event"),)

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
