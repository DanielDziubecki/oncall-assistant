# 7. Agents review PRs and merge what isn't critical

Date: 2026-11-22 · Status: accepted

## Context

The factory plan kept every merge for Daniel. Once factory agents open PRs, that makes him the bottleneck for changes that don't matter much. He wants agents to review PRs, tell him whether one needs his attention, and merge it when it isn't critical.

## Decision

- **A factory agent reviews each PR** and gives one verdict, with its reason: *needs Daniel* or *no action*. When unsure, the verdict is *needs Daniel*. The reviewer still doesn't edit files.
- **Daniel is notified of the verdict**, so he can tell from the notification whether to look (F3).
- **Agents may merge what isn't critical.** Critical changes stay with Daniel.
- **The verdict is not the only lock.** A PR's text can mislead a reviewer, so GitHub's rules enforce what is critical, outside the model.
- **Not yet.** This starts when the safety stages (F1, F2), notifications (F3), the coordinator (F4) and a reviewer proven on the bench (F6) exist. What counts as critical is decided then.

## Consequences

- Until then nothing changes: Daniel does every merge.
- `factory/rules.md` rule 6 (ask before merging) holds until Daniel changes it.
- GitHub doesn't let an account approve its own PR. Agent merges will need a second account or different branch rules, chosen in F6.
- A wrong *no action* can reach `main` unseen, so the bench must test the reviewer on changes that need Daniel, including PRs that argue they don't.
