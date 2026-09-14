---
name: Bug report
about: Something in the schema, fixtures, docs, or validator is wrong
title: "[Bug] "
labels: bug
assignees: ''
---

## Description

A clear description of what's wrong.

## Location

- File(s): (e.g. `schema/command.schema.json`, `fixtures/commands/invalid.json`,
  `scripts/validate_fixtures.py`)
- Line(s), if applicable:

## Expected vs. actual

What should happen, and what actually happens (include command output if
relevant, e.g. `python scripts/validate_fixtures.py` output).

## Impact

Does this affect a downstream implementer repo (`panopticon-response-engine`,
`panopticon-manager`, `panopticon-linux-agent`, `panopticon-agent`,
`panopticon-console`)? If so, which, and how?

## Suggested fix (optional)

If you have one.

---
**Security note**: if this bug has security implications (e.g. it means an
invalid or dangerous command could pass validation), please do not file it here
— report it privately per `SECURITY.md` instead.
