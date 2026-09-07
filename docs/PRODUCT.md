# Product overview

## Purpose

ReMind is a digital cognitive prosthetic that combines a trusted personal archive, a structured autobiographical knowledge graph, memory cards, a simplified timeline, and an evidence-grounded conversational assistant.

It is designed primarily for patients with memory impairment and secondarily for family members, caregivers, guardians, clinicians, and platform operators.

ReMind does not diagnose dementia or cognitive decline, replace professional care, prove uncertain historical facts, or invent missing details.

## Trust architecture

ReMind separates the product into five layers:

1. **Evidence:** original photographs, messages, recordings, documents, and metadata.
2. **Interpretation:** OCR, speech, vision, and entity/event extraction.
3. **Knowledge:** people, relationships, places, events, sources, and memories.
4. **Human verification:** review, correction, dispute resolution, consent, and sensitivity controls.
5. **Patient delivery:** timelines, memory cards, narration, and conversation.

AI may propose information in the interpretation and knowledge layers. Humans control verification. Only approved and releasable information belongs in patient delivery.

## Users

- **Patient:** views familiar memories, people, and places and asks simple questions.
- **Family contributor:** uploads and labels trusted source material.
- **Family reviewer:** verifies reconstructed memories and identities.
- **Caregiver:** assists the patient and can stop unsafe sessions.
- **Guardian:** manages delegated data authority within the patient's directive.
- **Clinician:** may view consented, non-diagnostic engagement information in validated deployments.
- **Administrator:** operates the platform without unrestricted patient-content access.

## MVP

The first controlled-testing milestone is a trusted family memory vault:

- Patient profiles and family accounts.
- Versioned and enforced consent.
- Secure photo upload and source provenance.
- Manual people and event tagging.
- Memory cards with evidence and review states.
- A simple patient timeline.
- Family review and sensitivity controls.
- Conversation limited to approved memories.
- Auditable corrections and complete deletion propagation.
- Basic accessibility and role-isolation testing.

Autonomous reconstruction is deliberately outside the initial milestone.

## Product language

Patient-facing copy should be calm and honest:

- “Let's look at this together.”
- “Your family has confirmed this memory.”
- “I don't have enough information about that yet.”

Avoid blaming the patient, exposing technical confidence language without context, or presenting medical conclusions.
