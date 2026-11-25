# Fix an external FastAPI ownership defect

[Documentation](../README.md) · English · [한국어](../i18n/ko/guides/REPOSITORY_HTTP_FIX.md)

`authzest repo-fix` is the 0.1.0 CLI flow for one self-contained FastAPI source file in another
local folder. It asks Codex for a GET PoC and a one-file repair, then checks the exact before and
after source in isolated A/B containers against cases you reviewed. Only after both checks pass
does it offer to write the original file, keeping a private backup. `authzest repo-restore` undoes
that write if you have not edited the file since. See the [frozen scope](../development/0.1.0-SCOPE.md).

Support: macOS arm64, Python 3.12 source installation and Docker Desktop with reviewed A/B images.
One flat `.py` app file, in-memory data, GET routes, explicit policy, synthetic identity headers
(`x-user`, `x-user-id`, `x-role`). No packages, databases, other HTTP methods or real login systems.

## 1. Preview the inputs and the case basis

```bash
authzest repo-fix /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --preview-only --json
```

This reads the two files only. It shows the exact request that would be shared and the `case_basis`
your case file must copy. Changing either file changes the basis.

## 2. Write the reviewed case file

The case file holds the expected answers. It stays on the host and is never sent to the model or to
a container. Use 4–8 GET cases with one designated regression, and cover owner access, non-owner
denial, normal use and, where applicable, anonymous denial and public routes:

```json
{
  "schema_version": "2.0",
  "kind": "repository-http-independent-cases",
  "basis": { "...": "copy case_basis from step 1" },
  "authorship": "Reviewed by <name> on <date>.",
  "assumptions": ["x-user carries a synthetic test identity."],
  "regression_case_id": "other",
  "regression_reason": "A non-owner must not read another user's note.",
  "coverage": {
    "owner": { "case_ids": ["owner"], "not_applicable_reason": null },
    "non-owner": { "case_ids": ["other"], "not_applicable_reason": null },
    "anonymous": { "case_ids": ["anonymous"], "not_applicable_reason": null },
    "normal-use": { "case_ids": ["normal"], "not_applicable_reason": null },
    "public": { "case_ids": [], "not_applicable_reason": "No public route." }
  },
  "cases": [
    {
      "id": "other",
      "request": {
        "method": "GET",
        "path": "/notes/1",
        "headers": { "x-user": "test-bob" }
      },
      "before": {
        "status": 200,
        "body": { "kind": "json", "value": { "id": 1 } }
      },
      "after": {
        "status": 403,
        "body": { "kind": "json", "value": { "detail": "Forbidden" } }
      }
    }
  ]
}
```

`before` is what the current code returns and `after` is what the policy requires. The model's PoC
must equal the designated regression request exactly, so name the synthetic users and object IDs in
the policy text. A case file is your review record, not authenticated approval.

## 3. Run the flow

```bash
authzest repo-fix /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --cases cases.json --runtime-profile ~/.authzest/runtime.json
```

Each effect asks for its own typed code, valid for 300 seconds; Enter declines and stops:

1. **share** – send the previewed source and policy to Codex for one proposal.
2. **copy** – create a fresh private copy; the original is untouched.
3. **run-before** – run the private before source in A, observe it from B and compare with your
   `before` answers. The designated regression must reproduce, or the flow stops.
4. **apply-private** – accept the exact diff and apply it to the private copy.
5. **run-after** – check the repaired copy against every `after` answer.
6. **apply-original** – recheck that the original and policy are unchanged since capture, keep a
   backup and write the repair. Any edit since capture is refused as a conflict. The replacement keeps
   the file's mode, group, ACL and extended attributes; a file owned by another user, with file
   flags, or whose metadata cannot be reproduced exactly is refused and left unchanged.

`--json` writes one final `repository-http-fix-result`; progress goes to stderr. Each phase keeps a
private evidence directory with its journal and full result.

## Results

| Status                                                 | Meaning                                                    |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| `original-applied`                                     | Both checks matched; the original now holds the repair.    |
| `original-declined`                                    | Both checks matched; you kept the original unchanged.      |
| `before-not-reproduced`                                | The before source did not show the reviewed defect.        |
| `after-not-verified`                                   | The repaired copy did not match every reviewed case.       |
| `poc-not-covered`                                      | The model's PoC differs from the designated regression.    |
| `original-conflict`                                    | The original or policy changed after capture; not written. |
| `*-phase-failed`, `original-recovery-required`, others | A step failed; read `failure` and the retained evidence.   |

`verified_fix: true` means the after check matched **your reviewed cases**. It does not certify the
whole application, a real authentication system or behaviour outside those requests.

## Recover the original

```bash
authzest repo-restore ~/.authzest/recovery/original-YYYYMMDDTHHMMSSZ-xxxxxxxx
```

The command shows the record and the file's current state, then asks for a typed code. It restores
the backup only while the file still equals the applied repair; if you edited it afterwards it
refuses and leaves your edits. The record directory keeps `before.py`, `after.py` and `record.json`.
