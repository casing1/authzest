# Branch protection

The active [Protect main ruleset](https://github.com/casing1/authzest/rules/22200692) applies to the
repository's default branch. Repository settings enforce these rules; this document describes the policy
and does not apply settings by itself.

- Changes must arrive through a pull request using a merge commit.
- The pull request must be up to date with the base branch, and review conversations must be resolved.
- The required checks are `python`, `frontend`, and `CodeQL`.
- The `CodeQL` result must come from GitHub Advanced Security (integration ID `57789`).
- Force pushes and branch deletion are blocked; no bypass actors are configured.
- Required approving reviews remain at zero for the current individual-development workflow.

CodeQL is configured through GitHub's existing default setup. Its pull-request result is required even
though it is not declared in `.github/workflows/ci.yml`. If the scan fails or reports a blocking finding,
resolve it before merging. Do not remove the requirement to get an unrelated change through.

When check names or scanning configuration change, verify the new check appears on a pull request before
updating the ruleset. Keep existing protections and record the change in a linked issue. Adding collaborators
is a suitable time to revisit the approving-review count.

GitHub documents the enforcement behavior in [available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).
