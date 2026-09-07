"""Pydantic schemas for consent (spec §17 directives, §24 third-party)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsentDirectiveCreate(BaseModel):
    """Sign a new version of the patient's consent directive.

    permissions/restrictions/guardian_rules are JSON documents describing
    what is allowed and what is off-limits; post_death_policy defines what
    happens to the archive after the patient passes.
    """

    permissions: dict = {}
    restrictions: dict = {}
    guardian_rules: dict = {}
    signer: str | None = None
    witness: str | None = None
    training_opt_in: bool = False
    post_death_policy: dict | None = None


class ConsentDirectiveOut(BaseModel):
    id: str
    patient_id: str
    version: int
    valid_from: datetime
    supersedes_id: str | None = None
    permissions: dict
    restrictions: dict
    guardian_rules: dict
    signer: str | None = None
    witness: str | None = None
    training_opt_in: bool
    post_death_policy: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThirdPartyConsentCreate(BaseModel):
    person_name: str = Field(min_length=1)
    person_id: str | None = None
    contact: str | None = None
    consent_given: bool = False
    notes: str | None = None


class ThirdPartyConsentUpdate(BaseModel):
    person_name: str | None = None
    person_id: str | None = None
    contact: str | None = None
    consent_given: bool | None = None
    notes: str | None = None


class ThirdPartyConsentOut(BaseModel):
    id: str
    patient_id: str
    person_id: str | None = None
    person_name: str
    contact: str | None = None
    consent_given: bool
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
