# URACE electronic waiver system — system description

<!-- Este documento está em inglês porque vai, como `system-description.md`, dentro do pacote de prova que o
advogado e o tribunal leem (#115). O passo a passo da equipe, em português, está no playbook geral
(docs/playbooks/playbook-geral.md, Site › Waiver). Mudou o sistema da waiver, muda este texto no mesmo PR. -->

This document describes how the URACE Command Center records a release and waiver of liability signed
electronically on URACE's own system (the "native waiver"), without DocuSign. It is versioned with the code: the
evidence package of each waiver carries this text together with the commit of the code that was running when the
package was exported.

- **Operator:** URACE.US INC, Orlando, Florida (go-kart racing school and track services).
- **Custodian of records:** Italo Jorge da Silveira (owner's decision, October 6, 2026; issue #115).
- **Time zone:** every time is stored in UTC and shown in Florida time (America/New_York, EDT/EST) and in UTC.

## 1. Screens

**Signer side (client portal, English):**

1. **Client account** (`/ops/portal`): the signer creates an account with full name, date of birth (18 or older),
   email, password, phone and address, and accepts the terms. The account's email is confirmed with a 6-digit code
   sent to it.
2. **Drivers:** the signer adds each driver with the date of birth. The date of birth decides the waiver: a minor
   gets the *Parental Consent, Release and Waiver of Liability*; an adult gets the *Adult Release and Waiver of
   Liability*. An adult driver who is not the account holder must sign their own waiver.
3. **Sign the waiver** (from the driver's card in the client portal): the real PDF of the template is drawn on screen, page by
   page; the consent boxes unlock only after every page has been shown. The signer then:
   - for a minor, states the relationship (mother or father only; a court-appointed guardian signs at the track with
     the court order) and accepts the declaration "I am the parent (natural guardian) of … and I have the authority to
     sign this waiver for them";
   - confirms that they read and understand English (or had the document translated);
   - checks "I have read this waiver and agree to its terms" and "I agree to sign electronically";
   - types the full name and draws the signature;
   - presses **Review before signing**: the server checks everything and shows a summary (document, driver, signer,
     relationship, typed name, signature image, valid until). If the typed name differs from the account name, the
     signer must confirm it;
   - receives a new one-time code by email and presses **I agree — sign the waiver**, with the statement of legal
     effect next to the button ("…the same legal effect as a handwritten signature").
4. **Invitation by email**: staff can email a personal, single-use link (valid 72 hours,
   bound to one client card) to the email on the client's card. The signer follows the same steps without an account;
   the one-time code goes to that same email.
5. **Signed waivers** (`/ops/portal/waivers`): the signer downloads the signed PDF and can ask for another copy by
   email. A copy is emailed automatically right after signing, from `noreply@urace.us`, with the signed PDF attached.

**Staff side (Command Center, Portuguese):**

- **Site › Waiver** (`/ops/site/waiver`, manager or above): turning online signing on or off (administrator only),
  the two templates and their versions, the status of the digital seal, the §744.301(3) notice check, and the list
  of signed waivers with **PDF**, **Trilha** (event trail), **Pacote de prova** (this evidence package), **Reenviar
  cópia** (email the copy again) and **Anular** (void, with a written reason).
- **Client card › Waivers** (operator or above): the waivers of that client, the invitation by email.
- **Balcão** (front desk, operator or above): at check-in, staff checks the signer's photo ID against the waiver
  (document type, name matches, minor's age matches). No image and no ID number is stored.

## 2. Authentication of the signer

- **Client account:** email and password (scrypt with a per-account salt; the password is never stored), session in
  an HttpOnly cookie (30 days; only the SHA-256 of the session token is stored). The account email must be confirmed
  with a one-time code before signing.
- **At the moment of signing:** a new 6-digit code is emailed to the account's (or the invitation's) email. It is valid
  for 15 minutes, 5 attempts, at most 5 codes per hour; only its hash is stored. The signature is recorded only after
  the code is confirmed. This shows that only the person with access to that mailbox could have signed (*Ruiz v.
  Moss Bros. Auto Group*; Fla. Stat. §668.50(9)).
- **Invitation link:** a random secret plus an HMAC seal, single use, valid 72 hours, bound to one client card and to
  the email, signer, driver and date of birth on the card when it was sent. Only the SHA-256 of the link is stored; if
  the card changes, the link stops working.
- **Reading the document:** the server requires that the template PDF was delivered to that account (or invitation)
  in the previous 24 hours, and records both the delivery time (server) and the "every page shown" time (reported by
  the browser).
- **Review before the final click** (Fla. Stat. §668.50(10)): the final click only signs with a review of the same
  account (or invitation) and driver, less than 30 minutes old, never used and with the same content (hash of name,
  signature, relationship, boxes and reading).

**Staff:** email and password (scrypt), HttpOnly session cookie with CSRF token, roles VIEWER < OPERATOR < MANAGER <
ADMIN. Every staff action on a waiver is recorded with the user.

## 3. Clock and NTP

- The server's clock is kept by NTP (`timedatectl` must show `System clock synchronized: yes` and `NTP service:
  active`). Every record stores UTC with milliseconds (`YYYY-MM-DDTHH:MM:SS.sssZ`).
- The time of the signature in the certificate is the server's time. Independently, the sealed PDF carries an RFC 3161
  time-stamp from an external time-stamping authority (TSA), so the time does not depend only on URACE's clock. Right
  after sealing, the system rejects a time-stamp more than 5 minutes away from the server's clock and tries the next
  TSA; `manage.py selo-waiver conferir` reports the difference between the server clock and the TSA.

## 4. Hashes (SHA-256)

- **Template:** the PDF of each template is imported, byte for byte, from URACE's DocuSign templates by an
  administrator, with its SHA-256. Every imported text is a version in `waiver_template_versions` (append-only); the
  signature stores the template's hash and version id.
- **Signed PDF:** the template, unchanged, plus a signature-and-certificate page (signer, driver, relationship and
  declaration, typed name, drawn signature, Florida and UTC times, IP, device, authentication, every step of the event
  history before signing, hashes). The SHA-256 of the final, sealed file is stored as `doc_sha256`.
- **Signature image:** the SHA-256 of the drawn PNG is stored in the trail and printed on the certificate page.
- **Event trail:** each event row stores `hash = SHA-256(prev_hash | canonical JSON of the row)`, chaining every event
  to the one recorded before it. A changed or removed row breaks the chain (`trilha_waiver.verificar`).

## 5. Digital seal (PAdES) and time-stamp (RFC 3161)

- The final PDF is sealed with a PAdES-B-T digital signature (SHA-256) by URACE's seal certificate, as a
  **certification** signature with DocMDP "no changes allowed", in the field `URACE-Seal`. Changing one byte of the
  file breaks the seal.
- The seal certificate is issued by URACE's own root ("URACE.US Waiver Seal Root"). The root's private key is used once,
  to issue the seal certificate, and is not kept. The public root certificate verifies every sealed PDF, including old
  ones. Adobe shows the identity as "unknown" (URACE's own certificate is not on Adobe's list); integrity and the
  time-stamp show as valid.
- The time-stamp comes from DigiCert (`http://timestamp.digicert.com`) and, if it does not answer in 10 seconds,
  FreeTSA (`https://freetsa.org/tsr`); the list is `CC_WAIVER_TSA`. Only a time-stamp whose authority chains to an
  accepted TSA root (DigiCert Trusted Root G4, pinned by SHA-256, and the `.pem` files of the TSA roots folder) is
  accepted. The token is kept inside the PDF and, byte for byte, in the append-only table `waiver_timestamps`.
- Without the seal or without a TSA, no waiver is signed: the signer reads "Online signing is temporarily
  unavailable…", nothing is recorded and the emailed code stays valid.

## 6. Where each thing is kept

| What | Where |
|---|---|
| Database (SQLite) | `~/.urace/command-center.sqlite` on URACE's server (VPS) |
| Signed waiver row (signer, dates, hash, trail) | table `waivers` (`source='urace'`) |
| Full trail, second copy | `audit_logs`, event `waiver.signed.trail`, written in the same transaction |
| Event trail | table `waiver_events` (hash-chained) |
| Time-stamp token | table `waiver_timestamps` |
| Review before the final click | table `waiver_reviews` |
| Void (with who, when and why) | table `waiver_voids` |
| Template versions | table `waiver_template_versions`; PDFs in `~/.urace/waivers/modelos/` (read-only, 0400) |
| Signed PDFs | `~/.urace/waivers/urace-<signature id>.pdf` (read-only, 0400) |
| Seal key and certificates | `~/.urace/waivers/selo/` (`seal-key.pem` 0600, `seal-cert.pem`, `root-cert.pem`; TSA roots in `tsa/`) — never in the code repository |
| Every staff and client action | `audit_logs` (append-only) |

## 7. Append-only records (database triggers)

The database itself refuses changes, not only the application:

- `waivers`: a native signed waiver cannot be updated (trigger `waivers_nativa_imutavel`, on every evidence column)
  nor deleted (`waivers_nativa_sem_apagar`). Only the link to a client card and the "hidden" flag can change.
- `audit_logs`, `waiver_events`, `waiver_timestamps`, `waiver_template_versions`, `waiver_voids`: no UPDATE and no
  DELETE (`*_no_update`, `*_no_delete`).
- `waiver_reviews`: the only change allowed is marking it used, once, in the signing transaction.

To take a waiver out of force, a manager **voids** it with a written reason: the waiver stays unchanged, in the list,
on the client card and in the backups, marked "voided".

## 8. How the IP address is captured

The server sits behind the Caddy web server on the same machine, which talks to the application over `127.0.0.1`.
Only a request coming from that trusted proxy (or from a network in `CC_PROXIES_CONFIAVEIS`) may state the client's
address in `X-Forwarded-For`, and the system reads that header **from right to left**, stopping at the first address
that is not a trusted proxy: the address the proxy itself saw. A value invented by the browser at the left of the
header is ignored. The same address is recorded in the trail, the audit log and the certificate.

## 9. After signing

Events after the signature (copy emailed, with the email provider's message-id, or the failure; photo ID checked at
the front desk; PDF downloaded; voided; evidence package exported) cannot be added to the sealed PDF. They are
recorded in the event trail with the waiver's id and appear in the certificate of completion of the evidence package
(`certificate-of-completion.pdf`).

## 10. Backups

- **Database:** every day at 03:15 a consistent copy (`VACUUM INTO`) is checked and kept on the server for 30 days, plus
  the first of each month for 12 months; at 04:00 the newest copy goes, encrypted (AES-256-GCM), to URACE's Google
  Drive. The restore path is tested on every code change.
- **Signed PDFs:** the Library (Biblioteca) copies every signed waiver, including hidden and voided ones, to URACE's
  Google Drive; a PDF whose hash no longer matches the one recorded at signing is not uploaded and the error is logged.
- **Seal key:** the seal folder is not in the database backup. The owner keeps a copy outside the server (in the
  owner's password manager). If the key is lost, old PDFs stay verifiable with the public root.

## 11. Who can access

| Role | Waiver access |
|---|---|
| Signer (client portal) | their own signed waivers: PDF and copy by email |
| Operator | client card waivers, invitations, copy by email, photo ID check at the front desk |
| Manager | Site › Waiver: signed list, event trail, **evidence package**, void |
| Administrator | everything above, importing templates, turning online signing on or off, the server |

The control panel is private (not indexed by search engines). Only the administrator works on the server itself.

## 12. Retention

Signed waivers are never deleted (owner's decision, October 6, 2026: "never delete"). A voided or expired waiver is
kept with the rest. Database backups follow §10.

## 13. The evidence package

A manager exports it in Site › Waiver › Assinadas › **Pacote de prova**. The ZIP contains the signed PDF, the trail as
stored, the event trail with the hash-chain check, the related audit-log rows (without passwords, cookies, tokens,
invitation links, email bodies or server folder paths), the template version, the time-stamp token, the public seal and TSA certificates,
a certificate of completion with every event (including after signing), this description, a draft declaration for
the attorney (FRE 902(11)/(13); Fla. Stat. §90.902(11)), `SHA256SUMS`, `VERIFY.md` and `verify_events.py`.

The event trail is checked against the record made at signing, not only against itself: each event before the
signature, and the signature event, are compared with the trail stored in the waiver's unchangeable row (`audit.json`,
whose last event hash is printed on the sealed PDF), and each later event with its own record (the void record, the
audit-log rows of the front-desk check and of the emailed copy). Anything that does not match is shown at the top of
the certificate of completion, in `events.json` and in `VERIFY.md`. The same record, exported by the
same version of the system (commit), produces the same ZIP, byte for byte; a new version changes the system
description and the draft declaration (and so the ZIP's SHA-256), not the records. Each export is recorded (`evidence_exported` in the event trail and
`waiver.evidence_export` in the audit log, with the ZIP's SHA-256).
