# Canonical Source Closure

The trusted source closure is generated from the release tree while excluding historical references, generated build/dist copies, VCS/cache files and bytecode caches. `references/` remains available for provenance and comparison but is non-authoritative.

Use:

```bash
python scripts/release/verify_rc12_2_1_source_closure.py
```

A qualification or promotion record should bind the `closure_digest` from `release/RC12_2_1_SOURCE_CLOSURE.json`, not an ad hoc working-directory hash.
