# Syncing from the legacy repository

`vincenti85/jongwoo-chemresearch` is the **canonical** repository. It carries the full
history of the earlier repository, but it is a standalone repository — **not** a GitHub
fork of it — so the "Sync fork" button and `gh repo sync`'s fork path do not apply here.
Use plain git remotes instead, as below.

| Repository | Role |
|---|---|
| `vincenti85/jongwoo-chemresearch` | **canonical** — all new work lands here |
| `jwleebest0823/chemresearch` | legacy — kept for reference; being archived |

Both repositories share the commit `1fd53fb` as a common ancestor, so git can merge or
cherry-pick between them without any history rewriting.

## Who can push

| Account | `vincenti85/jongwoo-chemresearch` |
|---|---|
| `vincenti85` | admin (owner) |
| `jwleebest0823` | **admin** — can create branches, open and merge PRs, and push to `main` |

No further access request is needed. If `git push` returns `403` or `404`, the cause is
almost always local credentials rather than repository permissions — check with
`gh auth status` that you are authenticated as the right account.

---

## Everyday work — clone the canonical repository directly

For all new work, this is the only thing you need:

```bash
git clone https://github.com/vincenti85/jongwoo-chemresearch.git
cd jongwoo-chemresearch
git checkout -b feat/<topic>
# ...work...
git push -u origin feat/<topic>
```

Then open a PR against `main`.

---

## Bringing changes over from the legacy repository

Use this when work exists in `jwleebest0823/chemresearch` (or in an old local clone of
it) that has not reached the canonical repository yet.

### 1. Add the legacy repository as a second remote

Run this once, inside a clone of the canonical repository:

```bash
git remote add legacy https://github.com/jwleebest0823/chemresearch.git
git fetch legacy
```

`git branch -r` should now list both `origin/*` and `legacy/*` branches. **Archiving the
legacy repository does not break this** — an archived repository stays publicly readable,
so `git fetch legacy` keeps working afterwards.

### 2. Put the legacy work on a branch of the canonical repository

```bash
git checkout -b sync/<topic> origin/main
git merge legacy/main            # or: git cherry-pick <sha>...
```

Resolve any conflicts here, on the branch — never directly on `main`.

### 3. Push and open a PR

```bash
git push -u origin sync/<topic>
gh pr create --base main --title "sync: <what came over>" --body "..."
```

Opening a PR rather than pushing straight to `main` is recommended even though you have
admin rights: it gives the other maintainer a chance to see what arrived, and it leaves a
record of where the change came from.

### Direct push to `main`

Permitted for both maintainers, and reasonable for small documentation fixes:

```bash
git push origin main
```

**Never force-push `main`.** `--force` on a shared branch discards the other maintainer's
commits with no warning and no recovery path through the GitHub UI. If a push is rejected
as non-fast-forward, the fix is `git pull --rebase` and re-push, not `--force`.

---

## Verifying the two repositories agree

```bash
git fetch origin && git fetch legacy
git log --oneline legacy/main..origin/main   # in canonical, not in legacy
git log --oneline origin/main..legacy/main   # in legacy, not in canonical
```

Both commands printing nothing means the two `main` branches are identical.
