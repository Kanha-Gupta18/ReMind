"""Pydantic schemas for consent (spec §17 directives, §24 third-party)."""

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.constants import ConsentAction, Role, SensitivityCategory, SourceType


class ConsentPermissions(BaseModel):
    """Actions and source types explicitly delegated by the patient."""

    allowed_data_sources: list[SourceType] = Field(default_factory=list)
    role_actions: dict[Role, list[ConsentAction]] = Field(default_factory=dict)
    third_party_visibility: Literal["consented_only", "family_reviewed"] = "consented_only"

    model_config = ConfigDict(extra="forbid")


class ConsentRestrictions(BaseModel):
    """Patient choices that downstream delivery and ingestion must honor."""

    prohibited_data_categories: list[SensitivityCategory] = Field(default_factory=list)
    blocked_person_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class GuardianRules(BaseModel):
    """Delegation recorded by the patient for one nominated guardian."""

    guardian_id: str | None = None
    authority: Literal["none", "shared", "delegated"] = "none"
    allowed_actions: list[ConsentAction] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def authority_requires_a_guardian(self):
        if self.authority == "none" and (self.guardian_id or self.allowed_actions):
            raise ValueError("guardian_id and allowed_actions require delegated guardian authority")
        if self.authority != "none" and not self.guardian_id:
            raise ValueError("shared or delegated authority requires guardian_id")
        return self


class PostDeathPolicy(BaseModel):
    mode: Literal["keep_private", "transfer_to_guardian", "delete"] = "keep_private"
    beneficiary_user_id: str | None = None
    retention_days: int | None = Field(default=None, ge=0, le=3650)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def transfer_requires_a_beneficiary(self):
        if self.mode == "transfer_to_guardian" and not self.beneficiary_user_id:
            raise ValueError("transfer_to_guardian requires beneficiary_user_id")
        if self.mode != "transfer_to_guardian" and self.beneficiary_user_id:
            raise ValueError("beneficiary_user_id is only valid for transfer_to_guardian")
        return self


class ConsentDirectiveCreate(BaseModel):
    """Sign a new version of the patient's consent directive.

    permissions/restrictions/guardian_rules are JSON documents describing
    what is allowed and what is off-limits; post_death_policy defines what
    happens to the archive after the patient passes.
    """

    permissions: ConsentPermissions = Field(default_factory=ConsentPermissions)
    restrictions: ConsentRestrictions = Field(default_factory=ConsentRestrictions)
    guardian_rules: GuardianRules = Field(default_factory=GuardianRules)
    signer: str | None = None
    witness: str | None = None
    training_opt_in: bool = False
    post_death_policy: PostDeathPolicy = Field(default_factory=PostDeathPolicy)

    @model_validator(mode="after")
    def guardian_actions_are_consent_scoped(self):
        allowed = set(self.permissions.role_actions.get(Role.GUARDIAN, []))
        if not set(self.guardian_rules.allowed_actions).issubset(allowed):
            raise ValueError("guardian allowed_actions must also be allowed for the guardian role")
        return self


class ConsentDirectiveOut(BaseModel):
    id: str
    patient_id: str
    version: int
    valid_from: datetime
    supersedes_id: str | None = None
    permissions: ConsentPermissions
    restrictions: ConsentRestrictions
    guardian_rules: GuardianRules
    signer: str | None = None
    signed_by_user_id: str | None = None
    witness: str | None = None
    training_opt_in: bool
    post_death_policy: PostDeathPolicy
    created_at: datetime

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
