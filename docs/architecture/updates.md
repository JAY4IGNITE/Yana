# Secure Update Architecture Specification

This document details the architectural design and security principles governing software updates for YANA on Windows 10 and 11.

---

## Core Security Invariants

1. **No Unsafe Self-Updating**: YANA will never automatically download and execute raw, unverified scripts or executables without cryptographic verification.
2. **Cryptographic Integrity & Authenticity**: All update packages must be signed with an Ed25519 private key during release generation. The desktop companion validates the signature against an embedded trusted public key before staging the update.
3. **Transport Security**: Update manifests and binaries are delivered exclusively over authenticated HTTPS channels with TLS certificate validation. Unencrypted HTTP, FTP, or local file schemes are unconditionally rejected.
4. **User Consent & Transparency**: Updates require user awareness and consent. The application presents release notes and version information before prompting the user to install.
5. **Atomic Staging**: Updates are staged to an isolated staging directory, validated via SHA-256 hash matching, and applied atomically to avoid partial or corrupted updates.

---

## Release Manifest Schema

The update service exposes an HTTPS manifest endpoint:
`https://updates.yana.local/v1/windows-x64/manifest.json`

```json
{
  "version": "0.2.0",
  "pub_date": "2026-10-01T12:00:00Z",
  "url": "https://releases.yana.local/packages/YANA-0.2.0-setup.exe",
  "signature": "d348a1...base64_ed25519_signature...",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "notes": "Feature update: enhanced voice synthesis and multi-window docking."
}
```

---

## Update Lifecycle Flow

```
+------------------+       1. Check for updates (HTTPS)        +--------------------+
|                  | ----------------------------------------> | Release Manifest   |
|  YANA Desktop    |                                           | Server             |
|  (Rust Core)     | <---------------------------------------- | (HTTPS Endpoint)   |
+------------------+       2. Return Manifest & Signature      +--------------------+
         |
         | 3. Compare Semver (Candidate > Current)
         | 4. Validate HTTPS URL & Verify Ed25519 Signature
         v
+------------------+       5. Notify User with Release Notes   +--------------------+
|  Settings Modal  | ----------------------------------------> | User Consent Modal |
|  (React UI)      |                                           | [Update] [Cancel]  |
+------------------+                                           +--------------------+
         |
         | 6. If confirmed: download to temporary staging
         | 7. Verify SHA-256 hash
         v
+------------------+
| Atomic Install   | -> Launches validated installer in CurrentUser mode
+------------------+
```

---

## Threat Modeling & Mitigation

| Threat Vector | Mitigation Strategy |
|---|---|
| **Man-in-the-Middle (MitM)** | Enforced HTTPS with strict TLS certificate verification; unencrypted HTTP rejected. |
| **Malicious Server Compromise** | Update payload must match Ed25519 cryptographic signature signed offline via release signing key. |
| **Tampered / Corrupted Binary** | SHA-256 cryptographic hash calculated and verified after download prior to execution. |
| **Silent Arbitrary Code Execution** | No silent background execution; updates require explicit user confirmation. |
| **Downgrade Attack** | Semantic version comparison rejects candidates with version <= current installed version. |
