"""Seed a ReMind user in the dev database so the web app has an account to log in with.

Run from services/api with the venv active:
    python scripts/seed_user.py patient@example.com "Pat Patient" patient
    python scripts/seed_user.py caregiver@example.com "Case Caregiver" caregiver --patient-id <patient_id>

A patient seeded with the default password is "password123".
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.constants import AccessGrantStatus, Role
from app.models.user import PatientAccessGrant, User

DEFAULT_PASSWORD = "password123"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a ReMind user in the dev database.")
    parser.add_argument("email")
    parser.add_argument("full_name")
    parser.add_argument("role", choices=[r.value for r in Role])
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--patient-id",
        default=None,
        help="users.id or the patient's email this account serves (for non-patient roles)",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == args.email).first()
        if existing:
            print(f"user {args.email} already exists (id={existing.id})")
            return
        patient_id = args.patient_id
        if patient_id and "@" in patient_id:
            patient = db.query(User).filter(User.email == patient_id).first()
            if patient is None:
                print(f"patient {patient_id} not found; seed the patient first")
                return
            patient_id = patient.id
        user = User(
            email=args.email,
            password_hash=hash_password(args.password),
            full_name=args.full_name,
            role=args.role,
        )
        db.add(user)
        db.flush()
        if patient_id:
            db.add(PatientAccessGrant(
                user_id=user.id,
                patient_id=patient_id,
                relationship=args.role.replace("_", " "),
                status=AccessGrantStatus.ACTIVE.value,
            ))
        db.commit()
        print(f"created {args.role} {args.email} (id={user.id})")


if __name__ == "__main__":
    main()
