[한국어 작성 안내](https://github.com/casing1/authzest/blob/main/docs/i18n/ko/PULL_REQUEST_TEMPLATE.md)

## Summary

<!-- What changed, and why is this the smallest useful change? -->

## Linked issue

Closes #

<!-- Set labels, include casing1 as an assignee without removing others, and match the linked issue's milestone.
If this is genuinely cross-milestone roadmap/process work, explain here why no milestone applies.
Read back the actual metadata; this template does not configure GitHub fields automatically. -->

## Verification

<!-- List the exact checks or manual scenarios used. -->

- [ ] Python tests
- [ ] Python lint and format checks
- [ ] Frontend lint, format, and build when relevant
- [ ] CLI or binary smoke test when relevant

## Security and compatibility

<!-- Describe security impact, new trust boundaries, external processes, or network access. Write "None" when not applicable. -->

## Checklist

- [ ] The change has one clear purpose and satisfies the issue acceptance criteria.
- [ ] Relevant labels and the `casing1` assignee are set on the issue and PR, preserving existing metadata.
- [ ] The milestone matches the linked issue, or an explicit cross-milestone reason is recorded; actual metadata was verified.
- [ ] Commits represent meaningful changes; behavior and its tests are kept together when practical.
- [ ] New or changed behavior has tests, or tests are not applicable to this documentation-only change.
- [ ] Any findings include source evidence and distinguish unknown from vulnerable.
- [ ] No secrets, personal data, build output, or unrelated changes are included.
- [ ] User-facing behavior and limitations are documented outside the README when appropriate.
- [ ] English documentation and its Korean counterpart are updated together; project README changes also
      update Japanese and Russian translations.
- [ ] New guides have reciprocal language links and appear in the English and Korean documentation indexes.
- [ ] Required `python`, `frontend`, and `CodeQL` checks pass before merging with a merge commit.
