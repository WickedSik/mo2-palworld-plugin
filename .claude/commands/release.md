---
description: Release a new version with semantic versioning (major.minor.patch)
args:
  - name: type
    description: Release type - patch (default), minor, or major
    required: false
---

You are executing a release workflow for MO2 Palworld Installer. This command updates the version, changelog, commits the changes, and creates a git tag.

**Release Type**: `{{type}}` (defaults to `patch` if empty or not specified)

## Execution Steps

### 1. Determine Release Type

Parse the release type from `{{type}}`:
- If empty, blank, or not specified: use `patch`
- Valid values: `patch`, `minor`, `major`
- If invalid value provided: abort with error message

### 2. Read Current Version

Read `plugins/PalworldInstaller/installer.py` and extract the current version from the `version()` method.

Expected line shape:

```python
return mobase.VersionInfo(MAJOR, MINOR, PATCH, mobase.ReleaseType.<TYPE>)
```

Example: `return mobase.VersionInfo(0, 2, 0, mobase.ReleaseType.PRE_ALPHA)`

Parse into components:
- MAJOR = first integer arg
- MINOR = second integer arg
- PATCH = third integer arg
- RELEASE_TYPE = the `mobase.ReleaseType.<TYPE>` token (preserve verbatim — do not auto-promote `PRE_ALPHA` → `ALPHA` → `FINAL` etc.)

This must be done by reading the file with the LLM and parsing the line — do **not** invoke `sed`, `awk`, regex shell pipelines, or any external script to mutate the version. The LLM is the source of truth for the bump.

### 3. Calculate New Version

Apply semantic versioning rules based on release type:

| Type | Operation | Example |
|------|-----------|---------|
| `patch` | Increment PATCH | 0.4.3 → 0.4.4 |
| `minor` | Increment MINOR, reset PATCH to 0 | 0.4.3 → 0.5.0 |
| `major` | Increment MAJOR, reset MINOR and PATCH to 0 | 0.4.3 → 1.0.0 |

### 4. Update installer.py

Use the `Edit` tool to replace the `VersionInfo(...)` call inside `plugins/PalworldInstaller/installer.py` with the new version, preserving the existing `mobase.ReleaseType.<TYPE>` token from step 2:

```python
return mobase.VersionInfo(X, Y, Z, mobase.ReleaseType.<TYPE>)
```

Rules:
- Do **not** change the `ReleaseType` value as part of a numeric bump. If the user wants to promote (e.g. `PRE_ALPHA` → `ALPHA` → `BETA` → `FINAL`), they will say so explicitly — otherwise leave it alone.
- Edit the file directly with the `Edit` tool. Do not generate scripts, `sed` invocations, or rely on regex tooling — the LLM performs the change.

### 5. Update CHANGELOG.md

Transform the `## [Unreleased]` section:

**Before:**
```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description
```

**After:**
```markdown
## [Unreleased]

## [X.Y.Z] - YYYY-MM-DD

### Added
- New feature description

### Fixed
- Bug fix description
```

Rules:
- Insert the new version header immediately after `## [Unreleased]`
- Add one blank line between `## [Unreleased]` and the new version header
- Use today's date in `YYYY-MM-DD` format
- Preserve all content that was under `[Unreleased]`
- The `[Unreleased]` section remains but becomes empty (ready for next development cycle)

### 6. Stage and Commit

Stage the modified files:
```bash
git add plugins/PalworldInstaller/installer.py CHANGELOG.md
```

Create commit with message:
```
Chore: Prepare release X.Y.Z
```

### 7. Create Git Tag

Create an annotated tag:
```bash
git tag vX.Y.Z
```

**Do NOT push** — the user will push manually when ready. Pushing the `vX.Y.Z` tag is what triggers `.github/workflows/release.yml`, which builds the `PalworldInstaller-X.Y.Z.zip` artifact and creates the GitHub Release with the matching `## [X.Y.Z]` changelog section as the body. Nothing in this command should attempt to build, package, or upload — that is exclusively the workflow's job.

## Output

After successful completion, display:

```
Release X.Y.Z prepared successfully!

Updated files:
  - plugins/PalworldInstaller/installer.py (VersionInfo X.Y.Z)
  - CHANGELOG.md ([Unreleased] → [X.Y.Z] - YYYY-MM-DD)

Git status:
  - Commit: "Chore: Prepare release X.Y.Z"
  - Tag: vX.Y.Z

Next steps:
  git push origin main --tags
```

## Error Handling

- **Invalid release type**: Display valid options and abort
- **Version parse failure**: Display the offending line from `plugins/PalworldInstaller/installer.py` and abort
- **Git operations fail**: Display error and suggest manual resolution
- **Files not found**: Display expected paths (`plugins/PalworldInstaller/installer.py`, `CHANGELOG.md`) and abort
