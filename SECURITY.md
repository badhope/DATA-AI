# Security Policy

Thanks for helping keep this project and its users safe. We take all
vulnerability reports seriously.

## Supported Versions

Only the latest release on the `main` branch receives security fixes.
Older versions are best-effort.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

**Please do not file a public issue.** Instead, report privately via one of:

- GitHub Security Advisories: open a
  [private security advisory](../../security/advisories/new) on this
  repository.
- Email: see the contact in `CITATION.cff` / the maintainer profile.

We aim to:

- acknowledge the report within **3 business days**,
- triage and reproduce within **10 business days**,
- ship a fix or a documented mitigation as soon as practical.

We follow responsible disclosure: we ask reporters to keep the issue
private until we publish a fix and a CVE / advisory, and we credit the
reporter in the advisory (unless you prefer to stay anonymous).

## Scope

In scope:

- code under this repository
- official container images and release artifacts published from this repo

Out of scope:

- third-party dependencies (report upstream unless we configured a
  pinned version that we shipped)
- social-engineering, physical, denial-of-service, or scanner spam

## Recognition

This project adheres to a "do the right thing" disclosure process.
We won't sue you for security research done in good faith.
