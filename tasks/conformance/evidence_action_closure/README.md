# Evidence--Action Closure Conformance Cases

These fixtures exercise the finite S0 gate, not model intelligence or physical
truth.

- `valid_revision.json`: independently grounded critical counterevidence
  changes the action, is re-tested, and permits promotion.
- `invalid_unacted_contradiction.json`: the same counterevidence is noticed but
  neither changes the action nor withdraws the claim; promotion must fail.
- `valid_withheld.json`: the unresolved contradiction is retained, but
  promotion is explicitly withheld, so the record is fail-safe.

Run the sovereign Lean checker with:

```bash
lake build evidenceActionCheck
.lake/build/bin/evidenceActionCheck \
  tasks/conformance/evidence_action_closure/valid_revision.json
```
