#!/usr/bin/env python3
"""End-to-end verification for the skill convention pivot (Step 1).

Builds a fully-isolated set of git repos + a temporary skill registry +
a temporary project_registry.yaml, then exercises every behavior the
plan calls for:

  1. Inventory walks ``agent-io/skills/`` first; legacy ``.claude/commands/``
     is discovered with a deprecation warning to stderr; both can
     coexist.
  2. ``sync <machine> --apply`` writes subscribed skills into the
     home_repo's ``.claude/commands/`` runtime dir AND into any
     ``deploys_to_repos`` targets (also runtime, gitignored).
  3. ``migrate-domain-skills --dry-run`` reports planned moves and
     gitignore additions without touching disk.
  4. ``migrate-domain-skills --apply`` performs ``git mv``, updates
     ``.gitignore``, and creates a single migration commit per repo.
  5. ``sync-repos --apply`` (no ``--commit``) writes files but creates
     NO commit; with ``--commit`` it produces a structured commit.
  6. ``sync-repos`` guards: home==target refused; dirty repo refused
     without ``--force``; wildcard expansion works.
  7. Real ClaudeCommands and AIAssistant state are never touched —
     CLAUDE_SKILLS_REGISTRY_PATH and CLAUDE_SKILLS_PROJECT_REGISTRY_PATH
     point everything at the temp fixture.

Usage::

    PYTHONPATH=. python scripts/verify_convention_pivot.py
    KEEP_TMP=1 PYTHONPATH=. python scripts/verify_convention_pivot.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WORKTREE = _HERE.parent
sys.path.insert(0, str(_WORKTREE))

import yaml  # noqa: E402


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def init_git_repo(path: Path, *, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q", "-b", "main"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test"], cwd=path)
    run(["git", "config", "commit.gpgsign", "false"], cwd=path)
    (path / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=path)
    run(["git", "commit", "-q", "-m", "init"], cwd=path)


def write_skill_md(
    path: Path,
    *,
    name: str,
    description: str,
    deploys_to_repos: list[str] | None = None,
    scope: str = "universal",
    extra_body: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm: dict = {"name": name, "description": description, "scope": scope}
    if deploys_to_repos is not None:
        fm["deploys_to_repos"] = deploys_to_repos
    yaml_block = yaml.safe_dump(fm, sort_keys=False).strip()
    body = f"# {name}\n\n{description}\n{extra_body}"
    path.write_text(f"---\n{yaml_block}\n---\n\n{body}", encoding="utf-8")


def manifest_hash_for(anchor: Path) -> str:
    from claude_skills.manifest import compute_manifest_hash

    return compute_manifest_hash(anchor)


def write_project_registry(path: Path, repos: dict[str, Path]) -> None:
    projects = {}
    for repo_name, repo_path in repos.items():
        pid = repo_name.lower()
        projects[pid] = {
            "name": repo_name,
            "type": "project",
            "status": "active",
            "priority": "high",
            "description": "",
            "parent": None,
            "children": [],
            "repo_path": str(repo_path),
            "working_dir": ".",
            "tags": [],
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"version": 2, "projects": projects}, sort_keys=False),
        encoding="utf-8",
    )


def write_skill_registry(path: Path, skills: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "skills": skills,
        "written_by_machine": "test",
        "written_at": "2026-05-06T00:00:00Z",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_eq(actual, expected, msg: str) -> None:
    if actual != expected:
        print(f"  FAIL: {msg}\n    expected: {expected!r}\n    actual:   {actual!r}", file=sys.stderr)
        sys.exit(1)


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def cli_invoke(env: dict, args: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "claude_skills.cli", *args]
    return subprocess.run(
        cmd, cwd=str(_WORKTREE), env=env, capture_output=True, text=True
    )


def head_message(repo: Path) -> str:
    return run(["git", "log", "-1", "--format=%B"], cwd=repo).stdout


def get_log_count(repo: Path) -> int:
    out = run(["git", "log", "--oneline"], cwd=repo).stdout
    return len([ln for ln in out.splitlines() if ln.strip()])


def make_registry_entry(
    *,
    name: str,
    description: str,
    home_repo: str,
    home_path: Path,
    deploys_to_repos: list[str],
    scope: str = "universal",
    domain: str | None = None,
) -> dict:
    return {
        "name": name,
        "description": description,
        "home_repo": home_repo,
        "home_path": str(home_path),
        "scope": scope,
        "domain": domain,
        "manifest_hash": manifest_hash_for(home_path),
        "retired": False,
        "conflict": False,
        "deploys_to_machines": [],
        "deploys_to_repos": deploys_to_repos,
        "last_deploy": {},
        "last_repo_deploy": {},
    }


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------


def scenario_inventory_walks_new_location(tmp: Path, env: dict) -> None:
    """Scenario 1: agent-io/skills/ wins over .claude/commands/.

    Build a synthetic 'home repo' with skill 'foo' under agent-io/skills/
    and skill 'bar' under .claude/commands/. Run ``inventory --apply``
    pointing at it via the temp project_registry. Confirm:

      - foo is registered with home_path under agent-io/skills/
      - bar is registered (legacy fallback)
      - a deprecation warning was emitted to stderr for the legacy path.
    """
    print("\n[1] inventory walks agent-io/skills/ first; legacy emits warning")

    repo = tmp / "FixtureRepo"
    init_git_repo(repo, name="FixtureRepo")

    write_skill_md(
        repo / "agent-io" / "skills" / "foo.md",
        name="Foo",
        description="primary skill",
        scope="domain",
    )
    write_skill_md(
        repo / ".claude" / "commands" / "bar.md",
        name="Bar",
        description="legacy skill",
        scope="domain",
    )

    project_registry = tmp / "state" / "project_registry.yaml"
    write_project_registry(project_registry, {"FixtureRepo": repo})

    # Empty starting registry.
    registry_path = tmp / "state" / "skill_registry.json"
    write_skill_registry(registry_path, {})

    env_local = dict(env)
    env_local["CLAUDE_SKILLS_REGISTRY_PATH"] = str(registry_path)
    env_local["CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"] = str(project_registry)

    ret = cli_invoke(env_local, ["inventory", "--apply"])
    assert_eq(ret.returncode, 0, "inventory --apply exit code")
    # Deprecation warning lands on stderr.
    assert_true(
        "legacy skill source" in ret.stderr or "WARNING" in ret.stderr,
        "deprecation warning expected on stderr",
    )

    reg = load_registry(registry_path)
    skills = reg.get("skills", {})

    assert_true("foo" in skills, "foo registered")
    assert_true("bar" in skills, "bar registered (legacy fallback)")
    foo_path = skills["foo"]["home_path"]
    bar_path = skills["bar"]["home_path"]
    assert_true(
        foo_path.endswith("agent-io/skills/foo.md"),
        f"foo home_path canonical, got {foo_path}",
    )
    assert_true(
        bar_path.endswith(".claude/commands/bar.md"),
        f"bar home_path legacy fallback, got {bar_path}",
    )


def scenario_sync_writes_runtime(tmp: Path, env: dict) -> None:
    """Scenario 2: sync --apply mirrors into <home>/.claude/commands/.

    Stage skill 'baz' in HomeRepo's agent-io/skills/. Build a fake system
    record in-process (so we don't have to monkey-patch state/systems.yaml),
    invoke ``claude_skills.sync.sync`` directly, and confirm baz lands in
    HomeRepo/.claude/commands/ AND in the fake user-global commands dir.
    """
    print("\n[2] sync --apply mirrors subscribed skills into per-repo runtime")

    repo = tmp / "HomeRepo"
    init_git_repo(repo, name="HomeRepo")

    skill_anchor = repo / "agent-io" / "skills" / "baz.md"
    write_skill_md(
        skill_anchor,
        name="Baz",
        description="runtime mirror skill",
        scope="domain",
    )

    project_registry = tmp / "state" / "project_registry_sync.yaml"
    write_project_registry(project_registry, {"HomeRepo": repo})

    registry_path = tmp / "state" / "skill_registry_sync.json"
    write_skill_registry(
        registry_path,
        {
            "baz": make_registry_entry(
                name="Baz",
                description="runtime mirror skill",
                home_repo="HomeRepo",
                home_path=skill_anchor,
                deploys_to_repos=[],
                scope="domain",
                domain="homerepo",
            )
        },
    )

    # Fake user-global runtime dir + system record.
    fake_user_root = tmp / "fake-user"
    (fake_user_root / ".claude").mkdir(parents=True, exist_ok=True)

    fake_system = {
        "machine_alias": "fixture-machine",
        "mode": "owned",
        "platform": "darwin",
        "description": "test machine",
        "claude_md_target": str(fake_user_root / ".claude" / "CLAUDE.md"),
        "commands_target": str(fake_user_root / ".claude" / "commands"),
        "tier2_source": None,
        "subscriptions": {"scopes": ["domain"], "domains": ["*"]},
    }
    # Write the fake system into a tier2 source path so get_tier2 has
    # something to resolve. tier2 reads from <repo>/systems/<name>/CLAUDE.md
    # by default; we provide an absolute tier2_source override below.
    fake_tier2 = tmp / "fake-tier2.md"
    fake_tier2.write_text("# fixture machine\n", encoding="utf-8")
    fake_system["tier2_source"] = str(fake_tier2)

    # Run sync via in-process Python so we can monkey-patch load_systems
    # without depending on env-var support that the systems module
    # doesn't currently provide.
    helper = (
        "import os, json, sys\n"
        f"sys.path.insert(0, {str(_WORKTREE)!r})\n"
        f"os.environ['CLAUDE_SKILLS_REGISTRY_PATH'] = {str(registry_path)!r}\n"
        f"os.environ['CLAUDE_SKILLS_PROJECT_REGISTRY_PATH'] = {str(project_registry)!r}\n"
        "from claude_skills import sync as _sync\n"
        f"_FAKE_SYSTEM = {fake_system!r}\n"
        "def _patched_load_systems():\n"
        "    return {'fixture-machine': _FAKE_SYSTEM}\n"
        "_sync.load_systems = _patched_load_systems\n"
        "plan = _sync.sync('fixture-machine', apply=True, init_claude_md=True)\n"
        "print(json.dumps({'applied': plan.get('applied'),"
        "    'runtime': list((plan.get('runtime_repos') or {}).keys()),"
        "    'errors': plan.get('errors', [])}))\n"
    )

    env_local = dict(env)
    result = subprocess.run(
        [sys.executable, "-c", helper],
        cwd=str(_WORKTREE),
        env=env_local,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("  sync invocation failed:", file=sys.stderr)
        print("  stdout:", result.stdout, file=sys.stderr)
        print("  stderr:", result.stderr, file=sys.stderr)
        sys.exit(1)

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert_true(payload["applied"], "sync applied=True")
    assert_true(
        "HomeRepo" in payload["runtime"],
        f"runtime mirror plan covers HomeRepo, got: {payload['runtime']!r}",
    )
    assert_eq(payload.get("errors", []), [], "no sync errors")

    runtime_anchor = repo / ".claude" / "commands" / "baz.md"
    assert_true(
        runtime_anchor.is_file(),
        f"baz mirrored to per-repo runtime at {runtime_anchor}",
    )

    user_anchor = fake_user_root / ".claude" / "commands" / "baz.md"
    assert_true(
        user_anchor.is_file(),
        f"baz also at user-global runtime {user_anchor}",
    )


def scenario_migrate_dry_run_then_apply(tmp: Path, env: dict) -> None:
    """Scenarios 3 and 4: migrate-domain-skills dry-run + apply."""
    print("\n[3-4] migrate-domain-skills dry-run + apply")

    repo = tmp / "MigrateRepo"
    init_git_repo(repo, name="MigrateRepo")

    legacy_anchor = repo / ".claude" / "commands" / "legacy-skill.md"
    write_skill_md(
        legacy_anchor,
        name="Legacy Skill",
        description="lives in legacy location",
        scope="domain",
    )
    # Sibling context dir.
    (repo / ".claude" / "commands" / "legacy-skill").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "commands" / "legacy-skill" / "context.md").write_text(
        "# legacy context\n", encoding="utf-8"
    )
    # Stage + commit so git mv has something to move.
    run(["git", "add", "-A"], cwd=repo)
    run(["git", "commit", "-q", "-m", "seed legacy skill"], cwd=repo)

    project_registry = tmp / "state" / "project_registry_migrate.yaml"
    write_project_registry(project_registry, {"MigrateRepo": repo})

    registry_path = tmp / "state" / "skill_registry_migrate.json"
    write_skill_registry(
        registry_path,
        {
            "legacy-skill": make_registry_entry(
                name="Legacy Skill",
                description="lives in legacy location",
                home_repo="MigrateRepo",
                home_path=legacy_anchor,
                deploys_to_repos=[],
                scope="domain",
                domain="migraterepo",
            )
        },
    )

    env_local = dict(env)
    env_local["CLAUDE_SKILLS_REGISTRY_PATH"] = str(registry_path)
    env_local["CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"] = str(project_registry)

    # Dry run.
    log_before = get_log_count(repo)
    ret = cli_invoke(env_local, ["migrate-domain-skills"])
    assert_eq(ret.returncode, 0, "migrate dry-run exit code")
    assert_true(
        "MigrateRepo" in ret.stdout,
        "migrate dry-run output includes MigrateRepo",
    )
    assert_true(
        "legacy-skill" in ret.stdout,
        "migrate dry-run mentions legacy-skill",
    )
    assert_true(
        legacy_anchor.is_file(),
        "dry-run leaves legacy file in place",
    )
    new_path = repo / "agent-io" / "skills" / "legacy-skill.md"
    assert_true(
        not new_path.exists(),
        "dry-run does not create new path",
    )
    assert_eq(get_log_count(repo), log_before, "dry-run creates no commit")

    # Apply.
    ret = cli_invoke(env_local, ["migrate-domain-skills", "--apply"])
    assert_eq(ret.returncode, 0, "migrate --apply exit code")
    assert_true(new_path.is_file(), "legacy-skill moved to agent-io/skills/")
    assert_true(
        not legacy_anchor.exists(),
        "legacy anchor removed after apply",
    )
    assert_true(
        (repo / "agent-io" / "skills" / "legacy-skill" / "context.md").is_file(),
        "sibling dir moved alongside anchor",
    )

    gi_text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert_true(".claude/commands/" in gi_text, ".gitignore has .claude/commands/")
    assert_true(".claude/skills/" in gi_text, ".gitignore has .claude/skills/")

    log_after = get_log_count(repo)
    assert_eq(log_after, log_before + 1, "apply creates one new commit")
    msg = head_message(repo)
    assert_true(
        "migrate skills source to agent-io/skills/" in msg,
        f"commit message format, got: {msg!r}",
    )

    # Registry home_path updated.
    reg = load_registry(registry_path)
    new_home = reg["skills"]["legacy-skill"]["home_path"]
    assert_true(
        new_home.endswith("agent-io/skills/legacy-skill.md"),
        f"registry home_path updated, got {new_home}",
    )

    # Idempotent: second --apply is a no-op.
    log_before_2 = get_log_count(repo)
    ret = cli_invoke(env_local, ["migrate-domain-skills", "--apply"])
    assert_eq(ret.returncode, 0, "second migrate --apply exit code")
    assert_eq(get_log_count(repo), log_before_2, "second --apply is no-op")


def scenario_sync_repos_no_commit_default(tmp: Path, env: dict) -> None:
    """Scenario 5: sync-repos writes files but does NOT commit by default.

    With ``--commit``, it produces a structured commit per repo.
    """
    print("\n[5] sync-repos --apply: no commit by default; --commit creates commit")

    home = tmp / "SyncReposHome"
    target = tmp / "SyncReposTarget"
    init_git_repo(home, name="SyncReposHome")
    init_git_repo(target, name="SyncReposTarget")

    anchor = home / "agent-io" / "skills" / "shared.md"
    write_skill_md(
        anchor,
        name="Shared",
        description="targets SyncReposTarget",
        deploys_to_repos=["SyncReposTarget"],
    )

    project_registry = tmp / "state" / "pr_syncrepos.yaml"
    write_project_registry(
        project_registry,
        {"SyncReposHome": home, "SyncReposTarget": target},
    )

    registry_path = tmp / "state" / "sr_syncrepos.json"
    write_skill_registry(
        registry_path,
        {
            "shared": make_registry_entry(
                name="Shared",
                description="targets SyncReposTarget",
                home_repo="SyncReposHome",
                home_path=anchor,
                deploys_to_repos=["SyncReposTarget"],
            )
        },
    )

    env_local = dict(env)
    env_local["CLAUDE_SKILLS_REGISTRY_PATH"] = str(registry_path)
    env_local["CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"] = str(project_registry)

    # Apply without --commit.
    log_before = get_log_count(target)
    ret = cli_invoke(env_local, ["sync-repos", "--apply"])
    assert_eq(ret.returncode, 0, "sync-repos --apply exit code")
    deployed = target / ".claude" / "commands" / "shared.md"
    assert_true(deployed.is_file(), "file written without --commit")
    assert_eq(
        get_log_count(target),
        log_before,
        "no commit when --commit is absent",
    )
    # The file is now an untracked/working-tree change in the target repo.
    # That's correct: post-pivot, .claude/commands/ is gitignored so nothing
    # to commit. For the --commit test we need a NEW skill that introduces
    # an actual change.

    # Reset target by removing the runtime file so the next sync-repos
    # treats it as a fresh add (and update the registry's
    # last_repo_deploy so removal logic doesn't kick in).
    deployed.unlink()
    sibling = target / ".claude" / "commands" / "shared"
    if sibling.is_dir():
        shutil.rmtree(sibling)
    # Also clear last_repo_deploy so the removal classification is empty.
    reg = load_registry(registry_path)
    reg["skills"]["shared"]["last_repo_deploy"] = {}
    write_skill_registry(registry_path, reg["skills"])

    # Now run with --commit; we expect the file to be added back AND
    # committed.
    ret = cli_invoke(env_local, ["sync-repos", "--apply", "--commit"])
    assert_eq(ret.returncode, 0, "sync-repos --apply --commit exit code")
    log_after = get_log_count(target)
    assert_true(
        log_after >= log_before + 1,
        f"--commit produced a new commit (before={log_before}, after={log_after})",
    )
    msg = head_message(target)
    assert_true(
        "claude-skills repo deploy" in msg,
        f"commit subject expected, got: {msg!r}",
    )
    assert_true(
        "Added: shared" in msg,
        f"commit body should list shared as added, got: {msg!r}",
    )


def scenario_sync_repos_guards(tmp: Path, env: dict) -> None:
    """Scenario 6: home==target refused, dirty repo refused, wildcard works."""
    print("\n[6] sync-repos guards: home==target refused, dirty refused, wildcard works")

    repo_a = tmp / "GuardA"
    repo_b = tmp / "GuardB"
    repo_c = tmp / "GuardC"
    for r, n in ((repo_a, "GuardA"), (repo_b, "GuardB"), (repo_c, "GuardC")):
        init_git_repo(r, name=n)

    skills_dir = tmp / "guard-skills"
    self_anchor = skills_dir / "self.md"
    wild_anchor = skills_dir / "wild.md"
    delta_anchor = skills_dir / "delta.md"
    write_skill_md(
        self_anchor,
        name="Self",
        description="should be refused",
        deploys_to_repos=["GuardA"],
    )
    write_skill_md(
        wild_anchor,
        name="Wild",
        description="targets all",
        deploys_to_repos=["*"],
    )
    write_skill_md(
        delta_anchor,
        name="Delta",
        description="for dirty test",
        deploys_to_repos=["GuardB"],
    )

    project_registry = tmp / "state" / "pr_guards.yaml"
    write_project_registry(
        project_registry,
        {"GuardA": repo_a, "GuardB": repo_b, "GuardC": repo_c},
    )

    registry_path = tmp / "state" / "sr_guards.json"
    write_skill_registry(
        registry_path,
        {
            "self": make_registry_entry(
                name="Self",
                description="should be refused",
                home_repo="GuardA",  # same as target — clobber!
                home_path=self_anchor,
                deploys_to_repos=["GuardA"],
            ),
            "wild": make_registry_entry(
                name="Wild",
                description="targets all",
                home_repo="GuardSource",  # not in registry → never clobbers
                home_path=wild_anchor,
                deploys_to_repos=["*"],
            ),
            "delta": make_registry_entry(
                name="Delta",
                description="for dirty test",
                home_repo="GuardSource",
                home_path=delta_anchor,
                deploys_to_repos=["GuardB"],
            ),
        },
    )

    env_local = dict(env)
    env_local["CLAUDE_SKILLS_REGISTRY_PATH"] = str(registry_path)
    env_local["CLAUDE_SKILLS_PROJECT_REGISTRY_PATH"] = str(project_registry)

    # 6a) Self-clobber refusal.
    ret = cli_invoke(
        env_local, ["sync-repos", "--apply", "--skill", "self"]
    )
    assert_true(
        ret.returncode != 0 or "would clobber" in (ret.stdout + ret.stderr).lower()
        or "home_repo" in (ret.stdout + ret.stderr).lower(),
        f"self-clobber should be refused (rc={ret.returncode}, "
        f"stdout={ret.stdout!r}, stderr={ret.stderr!r})",
    )
    assert_true(
        not (repo_a / ".claude" / "commands" / "self.md").exists(),
        "self.md NOT written to GuardA",
    )

    # 6b) Wildcard expansion: targets all 3 repos.
    ret = cli_invoke(
        env_local, ["sync-repos", "--apply", "--skill", "wild"]
    )
    assert_eq(ret.returncode, 0, "wildcard sync exit code")
    for r in (repo_a, repo_b, repo_c):
        assert_true(
            (r / ".claude" / "commands" / "wild.md").is_file(),
            f"wild.md present in {r.name}",
        )

    # 6c) Dirty-repo refusal.
    (repo_b / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")
    ret = cli_invoke(
        env_local,
        ["sync-repos", "--apply", "--skill", "delta", "--repo", "GuardB"],
    )
    # Should be skipped; the delta file should NOT be written.
    assert_true(
        not (repo_b / ".claude" / "commands" / "delta.md").exists(),
        "delta NOT written to dirty GuardB without --force",
    )
    assert_true(
        "SKIPPED" in ret.stdout or "skipped" in ret.stdout.lower(),
        f"dirty repo skipped, output: {ret.stdout!r}",
    )

    # 6d) --force overrides the dirty guard.
    ret = cli_invoke(
        env_local,
        [
            "sync-repos",
            "--apply",
            "--skill",
            "delta",
            "--repo",
            "GuardB",
            "--force",
        ],
    )
    assert_eq(ret.returncode, 0, "--force exit code")
    assert_true(
        (repo_b / ".claude" / "commands" / "delta.md").is_file(),
        "delta.md present in GuardB after --force",
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="claude-skills-pivot-"))
    print(f"  workdir: {tmp}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_WORKTREE) + os.pathsep + env.get("PYTHONPATH", "")
    # Redirect the deployment log into the temp tree so we don't pollute
    # the real ``state/deployment_log.jsonl`` while exercising sync.
    env["CLAUDE_SKILLS_DEPLOYMENT_LOG_PATH"] = str(tmp / "state" / "deployment_log.jsonl")

    try:
        scenario_inventory_walks_new_location(tmp, env)
        scenario_sync_writes_runtime(tmp, env)
        scenario_migrate_dry_run_then_apply(tmp, env)
        scenario_sync_repos_no_commit_default(tmp, env)
        scenario_sync_repos_guards(tmp, env)

        print("\n  OK: all scenarios passed.")
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\n  ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 2
    finally:
        if not os.environ.get("KEEP_TMP"):
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"\n  KEEP_TMP set; leaving {tmp} for inspection.")


if __name__ == "__main__":
    sys.exit(main())
