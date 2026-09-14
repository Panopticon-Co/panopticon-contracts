## Summary

<!-- One or two sentences: what does this change and why. -->

## Changes

<!-- Bullet list of what changed: schema, fixtures, docs, scripts, CI. -->

## Testing

<!-- What did you run? Paste relevant output. -->

- [ ] `python scripts/validate_fixtures.py` passes
- [ ] Every JSON file under `schema/` and `fixtures/` is syntactically valid
- [ ] (if applicable) `python scripts/validate_fixtures.py --grep-repos <paths>` run
      against local sibling checkouts

## Security Impact

<!-- Does this change any invariant in docs/SECURITY.md? Does it touch the
     closed 7-action set, target-shape validation, or the outcome/rejection
     vocabulary? If none, say "None." explicitly. -->

## Documentation

<!-- Which docs were updated: docs/CONTRACT.md, docs/VERSIONING.md,
     docs/SECURITY.md, docs/COMPATIBILITY.md, README.md, fixtures/README.md? -->

## Cross-Repository Impact

- [ ] If this changes a schema or enum, every consuming repo (agent,
      linux-agent, detection-engine, response-engine, manager, console) has
      been checked for compatibility.
- [ ] If breaking per `docs/VERSIONING.md`, `schema_version` was bumped and
      `docs/COMPATIBILITY.md` reflects the current per-repo status.

## Checklist

- [ ] No eighth action, and no `EXECUTE_COMMAND`/`RUN_SCRIPT`/`SHELL`/
      `FIREWALL_RULE`-shaped field or action was introduced.
- [ ] No validation logic in `scripts/validate_fixtures.py` was weakened.
- [ ] No out-of-scope infrastructure (queues, Kubernetes, a new runtime
      service, etc.) was introduced.
- [ ] Commit messages are focused and follow the repository's existing style.
