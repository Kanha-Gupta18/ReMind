"""Validated patient profile, onboarding, and relationship payloads."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.constants import ConsentAction, CognitionLevel, PatientProfileStatus, Role, SafetyLevel
from app.schemas.consent import ConsentDirectiveCreate, ConsentDirectiveOut


class AccessibilityProfile(BaseModel):
    text_size: Literal["standard", "large", "extra_large"] = "standard"
    high_contrast: bool = False
    reduced_motion: bool = False
    narration_auto_start: bool = False
    simplified_navigation: bool = True

    model_config = ConfigDict(extra="forbid")


class PatientProfileFields(BaseModel):
    preferred_name: str = Field(min_length=1, max_length=120)
    preferred_language: str = Field(default="en", min_length=2, max_length=35)
    accessibility_profile: AccessibilityProfile = Field(default_factory=AccessibilityProfile)
    date_of_birth: date | None = None
    diagnosis: str | None = Field(default=None, max_length=250)
    diagnosis_date: date | None = None
    cognition_level: CognitionLevel | None = None
    safety_level: SafetyLevel = SafetyLevel.NORMAL
    status: PatientProfileStatus = PatientProfileStatus.ACTIVE

    @model_validator(mode="after")
    def diagnosis_date_requires_diagnosis(self):
        if self.diagnosis_date is not None and not self.diagnosis:
            raise ValueError("diagnosis_date requires a diagnosis")
        return self


class PatientProfileCreate(PatientProfileFields):
    pass


class PatientProfileUpdate(BaseModel):
    preferred_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=35)
    accessibility_profile: AccessibilityProfile | None = None
    date_of_birth: date | None = None
    diagnosis: str | None = Field(default=None, max_length=250)
    diagnosis_date: date | None = None
    cognition_level: CognitionLevel | None = None
    safety_level: SafetyLevel | None = None
    status: PatientProfileStatus | None = None


class PatientProfileOut(PatientProfileFields):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientOnboardingRequest(BaseModel):
    profile: PatientProfileCreate
    consent: ConsentDirectiveCreate


class PatientOnboardingOut(BaseModel):
    profile: PatientProfileOut
    consent: ConsentDirectiveOut


class PatientCapabilitiesOut(BaseModel):
    actions: list[ConsentAction]


class RelationshipCreate(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    relationship: str = Field(min_length=1, max_length=80)


class RelationshipOut(BaseModel):
    id: str
    user_id: str
    patient_id: str
    full_name: str
    email: str
    role: Role
    relationship: str
    status: str
    granted_by: str | None
    created_at: datetime
    revoked_at: datetime | None
