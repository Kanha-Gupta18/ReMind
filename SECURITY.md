# Security policy

## Project status

ReMind is an early-stage prototype and is not approved for real patient, clinical, or otherwise sensitive personal data. Use synthetic or explicitly disposable development data only.

## Reporting a vulnerability

Do not open a public GitHub issue for a vulnerability that could expose personal data, authentication material, or server files. Contact the repository owner privately through the contact method on their GitHub profile and include:

- The affected route, component, or commit.
- Reproduction steps using synthetic data.
- Expected and observed behavior.
- Potential impact.
- A suggested mitigation, if known.

Never include real patient records, secrets, tokens, or uploaded personal media in a report.

## Security boundaries under development

The following areas are not production-ready:

- Consent enforcement across all data access.
- Source storage isolation, malware scanning, and encryption.
- Complete patient-delivery review gating.
- Identity-confirmation enforcement.
- Refresh-token revocation, MFA, session management, and recovery.
- Secure deletion and derived-data invalidation.
- Immutable audit retention and comprehensive access logging.
- Rate limiting, deployment hardening, and incident response.

## Secrets

- Keep `.env` files, credentials, tokens, production URLs, private keys, and uploaded data out of Git.
- Use the provided `.env.example` only as a local configuration template.
- Replace all example secrets and passwords in non-local environments.
- Use a secret manager for any deployed environment.
