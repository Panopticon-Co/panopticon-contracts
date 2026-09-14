# Contributing to panopticon-contracts

This repository is a versioned document + fixture set, not a runtime service.
Most contributions fall into one of two categories: clarifying/fixing
documentation, or changing the actual wire contract (schema, fixtures,
invariants). The two have different bars.

## Documentation-only changes

Fixing a typo, a broken link, a stale command, or clarifying existing behavior
in `README.md` / `docs/*.md` does not require a schema version bump and can be a
normal, small pull request. Do not use documentation changes to quietly redefine
behavior — if you find the docs and the actual implementation disagree, record
the discrepancy explicitly (as `docs/CONTRACT.md` already does throughout)
rather than "correcting" only one side.

## Changing the contract itself

This repository defines the contract; it does not implement it. A schema, enum,
or invariant change here is only half of the actual change — the other half is
every consuming repository staying compatible. Follow this process:

1. **Propose the change.** Open an issue (use the "Schema Change Proposal"
   template) describing exactly what is changing (a field, an action, a
   lifecycle transition, an `outcome` value, etc.), why, and whether it is
   additive or breaking per `docs/VERSIONING.md`. There is no separate RFC body
   or formal review board for this — the issue and subsequent pull request
   review are the process.
2. **Update the schema.** Edit `schema/command.schema.json` and/or
   `schema/command_result.schema.json`. Keep `additionalProperties: false` at
   every object level unless the change is specifically about relaxing that.
3. **Update the fixtures.** Add or update fixtures under `fixtures/` that make
   the new behavior concrete: at least one new valid example and, if the change
   introduces a new way to be invalid, a corresponding invalid/adversarial
   fixture. Follow the conventions in `fixtures/README.md` (fixed vs. variable
   fields, `$comment` grouping).
4. **Run the validator.**

   ```bash
   pip install -r requirements.txt
   python scripts/validate_fixtures.py
   ```

   This must pass before you open a pull request. If your change is genuinely
   breaking (see `docs/VERSIONING.md`'s Breaking list), also bump
   `schema_version` in both schema files and reflect the bump in
   `docs/CONTRACT.md` and `docs/VERSIONING.md`.
5. **Update the documentation that describes the change**: `docs/CONTRACT.md`
   (the canonical description), `docs/SECURITY.md` if the change touches an
   invariant, and `docs/COMPATIBILITY.md`'s per-repo matrix if you know a
   downstream repo's status changed as a result.
6. **Check every consuming repository for compatibility, in the same change.**
   Per this repository's own versioning policy, a breaking change ships as a
   coordinated update, not a rolling migration. Before merging, verify (or
   explicitly flag as follow-up work in the pull request description) the
   impact on:
   - `panopticon-response-engine` (canonical `Command`/`CommandResult`/lifecycle
     implementation)
   - `panopticon-manager` (dispatch, persistence, tiering/authorization)
   - `panopticon-linux-agent` (`command.hpp`/`command.cpp`)
   - `panopticon-agent` (`response/command.hpp`/`command.cpp`)
   - `panopticon-console` (anything rendering commands/results/lifecycle state)

   A pull request that changes a schema or enum without addressing this
   checklist will be asked to before merge — see the pull request template.
7. **Never add an eighth action**, an `EXECUTE_COMMAND`/`RUN_SCRIPT`/`SHELL`/
   `FIREWALL_RULE`-shaped action or field, or anything that would let `detail`
   or `target` carry raw command output, without a superseding ADR under
   `docs/adr/`. See `docs/adr/0001-panopticon-contracts.md` for why the action
   set is closed.

## Style

- Keep prose grounded in what the referenced implementation actually does, not
  an idealized or aspirational rewrite — `docs/CONTRACT.md` explicitly records
  discrepancies between documentation and code rather than silently picking one.
- Do not weaken `scripts/validate_fixtures.py`'s checks to make a change pass;
  fix the schema, fixture, or documentation instead.
- Avoid marketing language ("production-ready", "enterprise-grade", "AI-powered",
  invented benchmarks or certifications). This is a capstone/research security
  project — describe what it currently does and its known limitations plainly.

## Reporting a security issue

Do not open a public issue for a vulnerability — see `SECURITY.md`.
