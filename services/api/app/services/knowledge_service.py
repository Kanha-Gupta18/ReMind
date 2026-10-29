"""Canonical place and event records used by approved memories."""

from sqlalchemy.orm import Session

from app.models.knowledge import Event, Place


def create_place(
    db: Session, patient_id: str, actor_id: str, name: str,
    aliases: list[str] | None = None, description: str | None = None,
) -> Place:
    place = Place(
        patient_id=patient_id, created_by=actor_id, name=name.strip(),
        aliases=aliases or [], description=description,
    )
    db.add(place)
    db.flush()
    return place


def list_places(db: Session, patient_id: str) -> list[Place]:
    return (
        db.query(Place).filter(Place.patient_id == patient_id)
        .order_by(Place.name, Place.id).all()
    )


def create_event(
    db: Session, patient_id: str, actor_id: str, name: str,
    description: str | None = None, start_date=None, end_date=None,
    date_accuracy: str = "approximate",
) -> Event:
    event = Event(
        patient_id=patient_id, created_by=actor_id, name=name.strip(),
        description=description, start_date=start_date, end_date=end_date,
        date_accuracy=date_accuracy,
    )
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, patient_id: str) -> list[Event]:
    return (
        db.query(Event).filter(Event.patient_id == patient_id)
        .order_by(Event.start_date.asc().nullslast(), Event.name, Event.id).all()
    )
