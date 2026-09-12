<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/FIXTURE_APPLICATION.md">한국어</a>
</p>

# Approved application to an owned fixture copy

[Documentation index](../README.md) · [Proposal contract](../reference/PROPOSAL_CONTRACT.md)

## Scope and availability

#48 adds the next offline slice of #35 after #46. A source-checkout demo presents a fixed,
caller-authored `debug=True` → `debug=False` proposal and applies it only after an explicit decision.
It changes a **new private copy** of the maintained fixture, never the original checkout. This is not
AI-generated code, an authorization test, or a verified fix. The complete #35 workflow remains open.

The application helper currently requires supported POSIX file operations (tested locally on macOS
and in Python CI on Linux). Windows fails closed before creating a copy; this does not change existing
Windows scan/binary support. No product CLI/API command, version, dependency, report schema or alpha.2
release artifact changes. The older `scripts/demo_proposal.py` remains a no-application simulation.

## Run the interactive demo

From a source checkout with the development virtual environment active:

```bash
python -m scripts.demo_apply
python -m pytest tests/test_fixture_apply.py tests/test_fixture_apply_demo.py
```

The demo reads only the maintained `tests/fixtures/proposal_demo/main.py`, inventories source without
importing it, and creates a fresh `authzest-fixture-*` directory in the system temporary directory.
It prints the exact diff, proposal ID, copy location and verification plan. Type the complete displayed
`apply <proposal_id>` phrase to approve that proposal. Enter/incorrect text declines; `cancel`, EOF
or interruption while reading the prompt cancels. There is no `--yes` flag or arbitrary target argument.
Terminal text/JSON is escaped; the recorded decision is caller input, not authenticated human identity.

After a successful application, the demo shows exact restoration texts/hashes and asks separately for
`restore <proposal_id>`. Enter keeps the applied change. Restoration refuses detected later edits,
including file replacement with identical contents. It never writes back to the original fixture.
Decline/cancel is a normal exit; operational failures or stale state exit nonzero. All outcomes retain
`verification_status: not-run`: no provider, subprocess, scanned code, install hook or check is executed.

## Files and live-session guarantees

The core `FixtureApplySession` revalidates the request/review/proposal. It accepts exactly one selected
`main.py` and one replacement, without a Git revision claim. It creates its own fresh directory rather
than accepting an existing destination. `parent` only selects where a new directory is created.

- The copy directory is private (`0700`); `main.py`, `before.txt`, `after.txt` and `record.json` use `0600`.
  Before/after files contain exact UTF-8 bytes; hashes do not normalize CRLF or final newlines.
- The newest in-process approve/decline/cancel decision replaces the previous one. The session consumes
  it before an application attempt, checks its expiry again after staging, and does not accept external
  decision receipts. A fresh explicit choice is needed after a refused attempt; terminal failures end
  that session. A completed application cannot be replayed in the same session.
- Directory handles anchor operations. Bounded reads reject symlinks, hardlinks, nonregular files,
  changed permissions and changed file/directory identity. Content and metadata are checked before
  replacement; only a fully written, flushed staging file replaces `main.py` atomically.
- The journal retains proposal/decision identities, before/after hashes, lifecycle events and outcomes.
  Restoration uses the session's original bytes only if the current file still matches the applied
  content and identity. No automatic rollback overwrites a later edit.
- `close()` releases a handle, not data. Copies, snapshots and journals are deliberately retained;
  failed cleanup may leave a random `.stage-*` entry too. Inspect the printed workspace before deleting
  it yourself. The original checkout never needs a reset. Temporary storage is not a permanent backup.

## Failure meanings and limits

`applied` records that replacement occurred, not that a security property was verified. It stays true
after restoration as historical information; `restored: true` indicates the original copy was restored.
Post-write journal/durability/read failures are not reported as unchanged. An
`applied-state-unconfirmed` or `*-audit-failed` outcome requires manual inspection; a
`restoration-state-unconfirmed` result uses `restored: null`. A crash can leave an intent-only journal:
inspect actual bytes and snapshots, do not infer success or failure from the last phase alone.

This is a **single-process, exclusive-writer fixture-copy tool**, not an OS sandbox or a general patch
executor. Atomic replacement is not atomic compare-and-swap; a hostile/non-cooperating same-user process
can race the final check. Do not concurrently edit the copy during an operation. The directory's owner
can tamper with local records; they are not signed, authenticated or replay-proof credentials. There is
no restart/resume, automatic crash recovery, filesystem-wide transaction, arbitrary-checkout editing,
multi-file apply or persisted approval revocation service. Reopening a receipt cannot resume this session.

The separate [#50 Codex fixture command](CODEX_FIXTURE.md) adds opt-in source sharing and a narrowly
accepted model draft before these copy-only decisions. One owned-fixture live draft/apply/restore check
passed with user-authorized, assistant-entered approval phrases, not independent human review. This #48 demo remains
offline and scripted, with verification still `not-run`. #52 adds an optional, separately approved
fixed-source check to the Codex fixture flow, not this demo; it does not execute target source.
General repository integration and separately approved isolated runtime verification remain later #35
work. These slices do not complete the final acceptance gate or justify a release by themselves.
