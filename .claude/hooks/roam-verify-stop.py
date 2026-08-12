#!/usr/bin/env python3
# roam-hook-version: 15
"""roam verify -> Claude Code Stop-hook post-edit check.

Installed by `roam hooks claude --write`. QUIET-ON-COMPLETE-PASS: optional
reviewers fail open, but an edited stop blocks when the required Verify call
times out, returns malformed output, or reports incomplete evidence.

Fast-exit + block-rate telemetry (2026-07-11): a stop whose prompt-base
episode has no net source delta (committed, staged, unstaged, or untracked)
skips the verify subprocess. A commit made during the episode remains in scope
even when the current working tree is clean. Every decision appends a counts-only JSON line to
`.roam/hook-stops.jsonl` so the block rate is measurable -- see
_log_stop_event.

Feedback layer (all env-gated, all fail-open; defaults reproduce the
prior shipped behaviour when WHYFAIL+DOCDRIFT off and PROMINENT off):
  ROAM_HOOK_PROMINENT (default 1) -- present BLOCK-level (FAIL-severity)
      findings first and never truncate them, so a breaking-change /
      failed-test / hallucinated-import block is never buried behind
      style WARNs. Set 0 for the legacy flat findings[:8] list.
  ROAM_HOOK_WHYFAIL  (default 1) -- when an impacted test FAILED, attach
      roam why-fail's root-cause frame (recently-changed symbols the
      failing test transitively reaches, ranked by recency x PageRank)
      so the fix loop is tight instead of just "FAILED". Reuses the
      existing why-fail command; points at `roam diagnose` for a deeper
      single-symbol root cause.
  ROAM_HOOK_DOCDRIFT (default 0) -- when a public signature changed, add
      a soft advisory that docs/README may be stale (reuse:
      `roam doc-staleness` / `roam api-drift`). Advisory only -- it rides
      an existing block, never turns a clean PASS into noise.

Second-opinion reviewers (ALL default 0 / OFF, all fail-open, all
silent-when-clean, each reuses an existing roam command). They run
INDEPENDENTLY of the verify verdict so a diff that passes scoped verify
still gets the second opinion when an operator opts in. With every flag
at its default the hook output is byte-identical to the prior shipped
behaviour.
  ROAM_HOOK_CRITIQUE (default 0) -- pipe `git diff HEAD` to
      `roam critique`: a patch-vs-graph review (clone-siblings that need
      the same edit + high-blast-radius symbols) that scoped verify
      misses. Surfaces medium+ findings only. Closes F2.
  ROAM_HOOK_PRRISK   (default 0) -- attach `roam pr-risk`'s 0-100 diff
      risk score (blast x hotspot x bus-factor x coupling) when the diff
      ranks high/critical. Closes F19.
  ROAM_HOOK_ADVERSARIAL (default 0) -- attach `roam adversarial`'s high+
      architecture challenges (new cycles / layer violations) on the
      change. Closes F19.
  ROAM_HOOK_VIBE     (default 0) -- attach `roam vibe-check`'s AI-rot
      score when it crosses ROAM_HOOK_VIBE_THRESHOLD (default 50).
      Repo-scoped (not diff-scoped), so advisory only. Closes F23.
  ROAM_HOOK_REPORT_REFRESH (default 0) -- Loop B: on an edit-stop, spawn a
      DETACHED, THROTTLED (>= 6h) whole-repo `verify --report --persist` so the
      next compile's known_findings is fresh. Never blocks the stop; opt-in
      because it runs a background whole-repo verify.
"""
import json
import hashlib
import errno
import os
import secrets
import stat
import subprocess
import sys
import time

_VERIFY_TIMEOUT_S = 90
_WHYFAIL_TIMEOUT_S = 20
_CRITIQUE_TIMEOUT_S = 45
_PRRISK_TIMEOUT_S = 45
_ADVERSARIAL_TIMEOUT_S = 45
_VIBE_TIMEOUT_S = 60
_GITDIFF_TIMEOUT_S = 15
_GIT_CHECK_TIMEOUT_S = 10
_MAX_FAIL_SHOWN = 12
_MAX_OTHER_SHOWN = 8
_MAX_WHYFAIL_TESTS = 3
_MAX_WHYFAIL_SUSPECTS = 5
_MAX_CRITIQUE_SHOWN = 6
_MAX_ADVERSARIAL_SHOWN = 6
_PRRISK_WARN_RANK = 3  # warn only on high(3)/critical(4) diffs
_SIGCHANGE_CATS = ("breaking", "api", "api_drift", "api_changes")
# canonical severity ordering (roam.output._severity): higher = worse.
_SEV_RANK = {"info": 1, "note": 1, "low": 1, "medium": 2, "moderate": 2,
             "warning": 2, "high": 3, "error": 3, "critical": 4}
# BUG#62: the diff-scoped advisory detectors ship OFF by default, so the
# Stop-hook verify used to run "dark". Force the cheap, WARN-only advisory
# flags ON (heavy / hard-block-risk detectors -- CLONES / DELETE_CHECK /
# TAINT -- stay OFF). These never enter the verdict; they surface as a
# non-blocking notice.
_ADVISORY_ENV = {
    "ROAM_VERIFY_N1": "1",
    "ROAM_VERIFY_OVER_FETCH": "1",
    "ROAM_VERIFY_DEAD": "1",
    "ROAM_VERIFY_MAGIC_NUMBERS": "1",
    "ROAM_VERIFY_LLM_SMELLS": "1",
    "ROAM_VERIFY_TEST_HERMETICITY": "1",
    "ROAM_VERIFY_SMELLS": "1",
}
# Categories emitted by the advisory detectors above -- surfaced as a
# non-blocking notice, never as a decision:block.
_ADVISORY_CATEGORIES = frozenset({
    "n1", "over_fetch", "dead", "magic_numbers",
    "llm_smells", "test_hermeticity", "smells",
})
_EPISODE_SCHEMA = 1
_EPISODE_HOOK_VERSION = 15
_EPISODE_LOCK_ATTEMPTS = 20
_EPISODE_LOCK_SLEEP_S = 0.005
_EPISODE_LOCK_STALE_S = 30.0
_POLICY_MAX_FILE_BYTES = 4 * 1024 * 1024
_VERIFY_MAX_FILE_BYTES = 64 * 1024 * 1024
_VERIFY_MAX_TOTAL_BYTES = 256 * 1024 * 1024
_VERIFY_MAX_TARGETS = 4096
_VERIFY_MAX_ARG_CHARS = 128 * 1024
_POLICY_RELATIVE_PATHS = (
    ".roam/verify.yaml",
    ".roam/verify-baseline.json",
    ".roam/constitution.yml",
    ".roam/active_mode",
    ".roam-suppressions.yml",
    ".roam-gates.yml",
    ".roam-leak-patterns.py",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks/roam-compile-ups.py",
    ".claude/hooks/roam-verify-stop.py",
)


def _evidence_base(root, create=False):
    """Return the same out-of-repository evidence root as UserPromptSubmit."""
    override = (os.environ.get("ROAM_HOOK_EVIDENCE_DIR") or "").strip()
    if override:
        base = os.path.abspath(os.path.expanduser(override))
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = os.path.join(os.environ["LOCALAPPDATA"], "roam", "hook-evidence")
    else:
        state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
        base = os.path.join(state_home, "roam", "hook-evidence")
    try:
        repo_real = os.path.normcase(os.path.realpath(root))
        base_real = os.path.normcase(os.path.realpath(base))
        try:
            base_is_inside_repo = os.path.commonpath([repo_real, base_real]) == repo_real
        except ValueError:
            # Different Windows drive letters have no common path and are, by
            # construction, outside one another.
            base_is_inside_repo = False
        if base_is_inside_repo:
            return ""
        if create:
            os.makedirs(base_real, mode=0o700, exist_ok=True)
            if os.name != "nt":
                os.chmod(base_real, 0o700)
        if not os.path.isdir(base_real):
            return ""
        return base_real
    except OSError:
        return ""


def _episode_state_path(root, session_key):
    base = _evidence_base(root)
    if not base:
        return ""
    repo_key = hashlib.sha256(os.path.normcase(os.path.realpath(root)).encode("utf-8", "replace")).hexdigest()[:24]
    state_root = os.path.join(base, repo_key)
    if not os.path.isdir(state_root):
        return ""
    return os.path.join(state_root, session_key + ".json")


def _same_file_state(left, right, cross_handle=False):
    fields = ["st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"]
    if cross_handle and os.name == "nt":
        fields.remove("st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _policy_file_state(path):
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return "missing", True
    except OSError:
        return "unreadable", False
    if stat.S_ISLNK(before.st_mode):
        return "unsafe_symlink", False
    if not stat.S_ISREG(before.st_mode):
        return "not_regular", False
    if before.st_size > _POLICY_MAX_FILE_BYTES:
        return "too_large", False
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return "unreadable", False
    digest = hashlib.sha256()
    read_n = 0
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or not _same_file_state(before, opened, cross_handle=True):
            return "changed_during_hash", False
        while True:
            chunk = os.read(fd, 128 * 1024)
            if not chunk:
                break
            read_n += len(chunk)
            if read_n > _POLICY_MAX_FILE_BYTES:
                return "too_large", False
            digest.update(chunk)
        opened_after = os.fstat(fd)
        try:
            after = os.lstat(path)
        except OSError:
            return "changed_during_hash", False
        if (
            read_n != opened.st_size
            or not _same_file_state(opened, opened_after)
            or not _same_file_state(before, after)
        ):
            return "changed_during_hash", False
    finally:
        os.close(fd)
    return "sha256:" + digest.hexdigest(), True


def _policy_paths(root):
    paths = {"repo:" + rel: os.path.join(root, *rel.split("/")) for rel in _POLICY_RELATIVE_PATHS}
    runtime_file = os.path.abspath(globals().get("__file__") or sys.argv[0])
    runtime_dir = os.path.dirname(runtime_file)
    paths["runtime:user_prompt_hook"] = os.path.join(runtime_dir, "roam-compile-ups.py")
    paths["runtime:stop_hook"] = os.path.join(runtime_dir, "roam-verify-stop.py")
    paths["runtime:settings"] = os.path.join(os.path.dirname(runtime_dir), "settings.json")
    paths["user:settings"] = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    paths["user:settings_local"] = os.path.join(os.path.expanduser("~"), ".claude", "settings.local.json")
    return paths


def _policy_snapshot(root):
    manifest = []
    complete = True
    for label, path in sorted(_policy_paths(root).items()):
        state, ok = _policy_file_state(path)
        manifest.append([label, state])
        complete = complete and ok
    env_values = sorted(
        [name, value]
        for name, value in os.environ.items()
        if name == "ROAM_COMPILE_VERIFY" or name == "ROAM_REPO_LEAK_PATTERNS" or name.startswith("ROAM_VERIFY_")
    )
    manifest.append(["environment", env_values])
    payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), complete


def _episode_session_key(payload):
    session_id = str(payload.get("session_id") or "").strip()
    transcript_path = str(payload.get("transcript_path") or "").strip()
    stable = session_id or transcript_path
    if not stable:
        return "", session_id
    return hashlib.sha256(stable.encode("utf-8", "replace")).hexdigest()[:24], session_id


def _episode_lock(path):
    for _ in range(_EPISODE_LOCK_ATTEMPTS):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode("ascii", "replace"))
            return fd
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > _EPISODE_LOCK_STALE_S:
                    os.unlink(path)
                    continue
            except OSError:
                pass
            time.sleep(_EPISODE_LOCK_SLEEP_S)
        except OSError:
            return None
    return None


def _episode_unlock(path, fd):
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass


def _active_episode(payload):
    session_key, session_id = _episode_session_key(payload)
    if not session_key:
        return {"session_id": session_id, "evidence_required": False}
    root = _hook_repo_root()
    state_path = _episode_state_path(root, session_key)
    if not state_path:
        return {
            "session_id": session_id,
            "evidence_required": True,
            "evidence_error": "protected_episode_state_unavailable",
        }
    try:
        state_meta = os.lstat(state_path)
        if not stat.S_ISREG(state_meta.st_mode) or state_meta.st_size > 1024 * 1024:
            raise OSError("unsafe protected episode state")
        if os.name != "nt" and (
            state_meta.st_uid != os.getuid() or stat.S_IMODE(state_meta.st_mode) & 0o077
        ):
            raise OSError("unprotected episode state permissions")
    except OSError:
        return {
            "session_id": session_id,
            "evidence_required": True,
            "evidence_error": "protected_episode_state_unsafe",
        }
    lock_path = state_path + ".lock"
    fd = _episode_lock(lock_path)
    if fd is None:
        return {
            "session_id": session_id,
            "evidence_required": True,
            "evidence_error": "protected_episode_state_locked",
        }
    try:
        try:
            with open(state_path, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
        expected_repo = hashlib.sha256(
            os.path.normcase(os.path.realpath(root)).encode("utf-8", "replace")
        ).hexdigest()
        if (
            not isinstance(state, dict)
            or state.get("state_schema") != "roam.hook.episode.v2"
            or state.get("repo_sha256") != expected_repo
        ):
            return {
                "session_id": session_id,
                "evidence_required": True,
                "evidence_error": "protected_episode_state_invalid",
            }
        active = state.get("active") if isinstance(state, dict) else {}
        if not isinstance(active, dict):
            return {
                "session_id": session_id,
                "evidence_required": True,
                "evidence_error": "protected_episode_state_missing",
            }
        return {
            "session_id": str((state or {}).get("session_id") or session_id),
            "episode_id": str(active.get("episode_id") or ""),
            "turn_seq": active.get("turn_seq"),
            "started_at_ms": active.get("started_at_ms"),
            "base_head": active.get("base_head"),
            "base_head_state": active.get("base_head_state"),
            "policy_sha256": active.get("policy_sha256"),
            "policy_complete": active.get("policy_complete"),
            "evidence_required": True,
            "_state_path": state_path,
            "_state": state,
        }
    finally:
        _episode_unlock(lock_path, fd)


def _clear_active_episode(active):
    state_path = str(active.get("_state_path") or "")
    episode_id = str(active.get("episode_id") or "")
    if not state_path or not episode_id:
        return
    lock_path = state_path + ".lock"
    fd = _episode_lock(lock_path)
    if fd is None:
        return
    try:
        try:
            with open(state_path, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
        current = state.get("active") if isinstance(state, dict) else {}
        if not isinstance(current, dict) or str(current.get("episode_id") or "") != episode_id:
            return
        state["active"] = None
        tmp = state_path + ".tmp-%d-%d" % (os.getpid(), time.time_ns())
        try:
            tmp_fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, sort_keys=True, separators=(",", ":"))
                fh.write(chr(10))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, state_path)
            if os.name != "nt":
                os.chmod(state_path, 0o600)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass
    finally:
        _episode_unlock(lock_path, fd)


def _append_episode_event(event):
    root = _hook_repo_root()
    log_dir = os.path.join(root, ".roam")
    if not os.path.isdir(log_dir):
        return
    log_path = os.path.join(log_dir, "episodes.jsonl")
    try:
        if os.path.exists(log_path) and os.path.getsize(log_path) > 10 * 1024 * 1024:
            return
    except OSError:
        return
    lock_path = log_path + ".lock"
    fd = _episode_lock(lock_path)
    if fd is None:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + chr(10))
    finally:
        _episode_unlock(lock_path, fd)


def _record_episode_stop(payload, active, outcome, terminal, blocked, verify_ms, skipped_no_edit, diff_identity):
    episode_id = str(active.get("episode_id") or "")
    if not episode_id:
        seed = "%s:%d:%d" % (str(payload.get("session_id") or "orphan"), time.time_ns(), os.getpid())
        episode_id = "orphan_" + hashlib.sha256(seed.encode("utf-8", "replace")).hexdigest()[:20]
    now_ms = int(time.time() * 1000)
    try:
        duration_ms = max(0, now_ms - int(active.get("started_at_ms")))
    except (TypeError, ValueError):
        duration_ms = None
    event_type = "stop_continuation" if payload.get("stop_hook_active") else "stop_decision"
    if outcome == "verified_clean":
        health_state = "verification_passed"
    elif outcome in ("verification_blocked", "verification_failed_without_findings"):
        health_state = "verification_failed"
    elif outcome in (
        "verify_unavailable",
        "policy_evidence_unavailable",
        "policy_tampering",
        "verification_race",
    ):
        health_state = "verification_unavailable"
    elif outcome == "continued_after_block":
        health_state = "continuation_unverified"
    else:
        health_state = "not_applicable"
    event = {
        "schema_version": _EPISODE_SCHEMA,
        "hook_version": _EPISODE_HOOK_VERSION,
        "evidence_source": "live_hook",
        "event_id": "evt_" + hashlib.sha256(
            ("%s:%s:%d" % (episode_id, event_type, time.time_ns())).encode("utf-8")
        ).hexdigest()[:24],
        "episode_id": episode_id,
        "event_type": event_type,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(active.get("session_id") or payload.get("session_id") or ""),
        "turn_seq": active.get("turn_seq"),
        "terminal": bool(terminal),
        "outcome": outcome,
        "duration_ms": duration_ms,
        "blocked": bool(blocked),
        "verify_ms": int(verify_ms),
        "skipped_no_edit": bool(skipped_no_edit),
        "changed_files": diff_identity.get("changed_files"),
        "diff_sha256": str(diff_identity.get("diff_sha256") or ""),
        "base_head": str(active.get("base_head") or ""),
        "base_head_state": str(active.get("base_head_state") or ""),
        "health_state": health_state,
    }
    _append_episode_event(event)
    if terminal:
        _clear_active_episode(active)
    return event


def _env_on(name, default):
    return (os.environ.get(name, default) or "").strip().lower() not in ("", "0", "false", "no", "off")


_REPORT_REFRESH_HOURS = 6.0
_REFRESH_CLAIM_MINUTES = 30.0  # single-flight window: at most one spawn per claim age


def _hook_repo_root():
    """Nearest ancestor (cwd included) containing .git; cwd when none found.

    The spawned verify persists at the PROJECT ROOT (find_project_root walks
    up to .git) — the throttle and claim must anchor to the same directory,
    or a hook run from a repo subdir respawns on every stop forever.
    """
    d = os.getcwd()
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.getcwd()
        d = parent


def _git_current_head(root):
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=root,
            capture_output=True, text=True, timeout=_GIT_CHECK_TIMEOUT_S,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return "", "unavailable"
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=root,
            capture_output=True, text=True, timeout=_GIT_CHECK_TIMEOUT_S,
        )
        if head.returncode != 0:
            return "", "unborn"
        value = head.stdout.strip().lower()
        if len(value) not in (40, 64) or any(ch not in "0123456789abcdef" for ch in value):
            return "", "unavailable"
        return value, "present"
    except Exception:
        return "", "unavailable"


def _decode_git_paths(raw):
    paths = []
    for value in raw.split(bytes((0,))):
        if not value:
            continue
        path = os.fsdecode(value).replace("\\", "/")
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in path):
            return None
        if path.startswith("/") or os.path.isabs(path) or ".." in path.split("/"):
            return None
        if path == ".roam" or path.startswith(".roam/") or path == ".claude" or path.startswith(".claude/"):
            continue
        paths.append(path)
    return paths


def _git_name_bytes(root, args):
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True,
            timeout=_GITDIFF_TIMEOUT_S,
        )
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _verification_scope_paths(root, active):
    """Resolve the full episode delta, including commits made after prompt."""
    if active.get("evidence_required"):
        if active.get("evidence_error"):
            return None, str(active.get("evidence_error"))
        base_head = active.get("base_head")
        base_state = active.get("base_head_state")
        if base_state == "present":
            if (
                not isinstance(base_head, str)
                or len(base_head) not in (40, 64)
                or any(ch not in "0123456789abcdef" for ch in base_head)
            ):
                return None, "episode_base_head_invalid"
        elif base_state == "unborn":
            base_head = ""
        else:
            return None, "episode_base_head_unavailable"
    else:
        base_head, base_state = _git_current_head(root)
        if base_state == "unavailable":
            return None, "git_head_unavailable"

    raw_paths = []
    if base_state == "present":
        changed = _git_name_bytes(
            root,
            ["diff", "--no-ext-diff", "--name-only", "-z", "--no-renames", base_head, "--"],
        )
        if changed is None:
            return None, "episode_diff_unavailable"
        decoded = _decode_git_paths(changed)
        if decoded is None:
            return None, "episode_path_decode_failed"
        raw_paths.extend(decoded)
    else:
        # An unborn base means every currently tracked path was created during
        # the episode. `ls-files --cached` continues to cover it after a commit.
        tracked = _git_name_bytes(root, ["ls-files", "--cached", "-z"])
        if tracked is None:
            return None, "episode_index_scope_unavailable"
        decoded = _decode_git_paths(tracked)
        if decoded is None:
            return None, "episode_path_decode_failed"
        raw_paths.extend(decoded)

    untracked = _git_name_bytes(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    if untracked is None:
        return None, "episode_untracked_scope_unavailable"
    decoded = _decode_git_paths(untracked)
    if decoded is None:
        return None, "episode_path_decode_failed"
    raw_paths.extend(decoded)
    paths = sorted(set(path.strip() for path in raw_paths if path.strip()))
    if len(paths) > _VERIFY_MAX_TARGETS or sum(len(path) + 1 for path in paths) > _VERIFY_MAX_ARG_CHARS:
        return None, "episode_scope_too_large"
    return paths, None


def _scope_sha256(paths):
    payload = json.dumps(sorted(set(paths)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verification_content_sha256(root, paths):
    """Mirror Verify receipt-v3 hashing: exact bytes, missing markers, no symlinks."""
    try:
        canonical_root = os.path.realpath(root)
        if not os.path.isdir(canonical_root):
            return None, "verification_root_unavailable"
    except OSError:
        return None, "verification_root_unavailable"
    manifest = []
    total_bytes = 0
    for relative_path in sorted(set(paths)):
        candidate = os.path.join(canonical_root, *relative_path.split("/"))
        try:
            if os.path.commonpath([canonical_root, os.path.abspath(candidate)]) != canonical_root:
                return None, "scope_path_outside_root"
        except ValueError:
            return None, "scope_path_outside_root"
        parent = os.path.dirname(candidate)
        if not os.path.exists(parent):
            manifest.append([relative_path, "missing"])
            continue
        try:
            canonical_parent = os.path.realpath(parent)
            if os.path.commonpath([canonical_root, canonical_parent]) != canonical_root:
                return None, "scope_path_outside_root"
        except (OSError, ValueError):
            return None, "scope_file_unreadable"
        try:
            path_before = os.lstat(candidate)
        except FileNotFoundError:
            manifest.append([relative_path, "missing"])
            continue
        except OSError:
            return None, "scope_file_unreadable"
        if stat.S_ISLNK(path_before.st_mode):
            return None, "scope_file_symlink"
        if not stat.S_ISREG(path_before.st_mode):
            return None, "scope_file_not_regular"
        if path_before.st_size > _VERIFY_MAX_FILE_BYTES:
            return None, "scope_file_too_large"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(candidate, flags)
        except OSError as exc:
            return None, "scope_file_symlink" if exc.errno == errno.ELOOP else "scope_file_unreadable"
        digest = hashlib.sha256()
        bytes_read = 0
        try:
            opened_before = os.fstat(fd)
            if not stat.S_ISREG(opened_before.st_mode) or not _same_file_state(
                path_before, opened_before, cross_handle=True
            ):
                return None, "scope_file_changed_during_hash"
            while True:
                chunk = os.read(fd, 256 * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > _VERIFY_MAX_FILE_BYTES:
                    return None, "scope_file_too_large"
                digest.update(chunk)
            opened_after = os.fstat(fd)
            try:
                path_after = os.lstat(candidate)
            except OSError:
                return None, "scope_file_changed_during_hash"
            if (
                bytes_read != opened_before.st_size
                or not _same_file_state(opened_before, opened_after)
                or not _same_file_state(path_before, path_after)
            ):
                return None, "scope_file_changed_during_hash"
        finally:
            os.close(fd)
        total_bytes += bytes_read
        if total_bytes > _VERIFY_MAX_TOTAL_BYTES:
            return None, "verification_scope_too_large"
        manifest.append([relative_path, "sha256:" + digest.hexdigest()])
    payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), None


def _scope_status_sha256(root, paths):
    head, head_state = _git_current_head(root)
    if head_state == "unavailable":
        return None, "git_head_unavailable"
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths],
            cwd=root, capture_output=True, timeout=_GITDIFF_TIMEOUT_S,
        )
    except Exception:
        return None, "git_status_unavailable"
    if proc.returncode != 0:
        return None, "git_status_unavailable"
    digest = hashlib.sha256()
    digest.update(head_state.encode("ascii"))
    digest.update(bytes((0,)))
    digest.update(head.encode("ascii"))
    digest.update(bytes((0,)))
    digest.update(proc.stdout)
    return digest.hexdigest(), None


def _verification_snapshot(root, active):
    paths, error = _verification_scope_paths(root, active)
    if error:
        return None, error
    scope_sha = _scope_sha256(paths)
    content_sha, error = _verification_content_sha256(root, paths)
    if error:
        return None, error
    status_sha, error = _scope_status_sha256(root, paths)
    if error:
        return None, error
    return {
        "paths": paths,
        "scope_sha256": scope_sha,
        "content_sha256": content_sha,
        "status_sha256": status_sha,
        "target_file_count": len(paths),
    }, None


def _same_verification_snapshot(left, right):
    return bool(left) and bool(right) and all(
        left.get(key) == right.get(key)
        for key in ("paths", "scope_sha256", "content_sha256", "status_sha256", "target_file_count")
    )


def _maybe_refresh_whole_repo_report():
    """Loop B: keep .roam/verify-report.json fresh so `compile`'s known_findings
    probe can embed the repo's OPEN findings for the edited file.

    DETACHED + THROTTLED + SINGLE-FLIGHT + fail-open, by hard requirement:
      - detached: a whole-repo `verify --report` is ~minutes; running it inline
        would blow the Stop-hook budget (it is the exact stall the diff-only
        scope avoids). We fire-and-forget and never read its result here.
      - never --diff-only: that persists a diff-SCOPED view into the whole-repo
        report path, poisoning known_findings. This is a SEPARATE whole-repo run.
      - throttled: skip if the report is younger than _REPORT_REFRESH_HOURS.
      - single-flight: a claim marker bounds spawning to one verify per
        _REFRESH_CLAIM_MINUTES per repo. The report mtime alone cannot close
        the in-flight window (it only moves AFTER the ~minutes-long verify
        persists), and it never moves at all when the persist cannot land
        (empty targets, missing DB, crash) — without the claim every edit-stop
        would respawn a whole-repo verify, each re-running ensure_index().
    Opt-in (ROAM_HOOK_REPORT_REFRESH, default OFF): it spawns a background
    whole-repo verify, so enabling it is the user's call; enabling closes Loop B.
    """
    if not _env_on("ROAM_HOOK_REPORT_REFRESH", "0"):
        return
    try:
        root = _hook_repo_root()
        report = os.path.join(root, ".roam", "verify-report.json")
        try:
            if (time.time() - os.path.getmtime(report)) / 3600.0 < _REPORT_REFRESH_HOURS:
                return  # fresh enough — don't respawn every edit-stop
        except OSError:
            pass  # missing/unreadable -> refresh
        claim = os.path.join(root, ".roam", "verify-refresh-claim")
        try:
            if (time.time() - os.path.getmtime(claim)) / 60.0 < _REFRESH_CLAIM_MINUTES:
                return  # a refresh is (or was recently) in flight
        except OSError:
            pass  # no claim yet
        os.makedirs(os.path.join(root, ".roam"), exist_ok=True)
        with open(claim, "w") as fh:
            fh.write("pid=%d time=%d" % (os.getpid(), int(time.time())))  # observability crumb
        kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        # whole-repo (NO --diff-only) --report --persist -> <root>/.roam/verify-report.json
        # cwd=root pins the spawned verify's project-root resolution to the SAME
        # directory the throttle checked.
        subprocess.Popen(
            ["roam", "--override-mode", "verify", "--auto", "--report", "--persist"],
            cwd=root,
            **kwargs,
        )
    except Exception:
        return  # a refresh we could not spawn is never the user's problem


def _run_roam(args, timeout, env=None):
    """Run `roam --json <args>`; return the parsed envelope or None."""
    try:
        # Verify/index are hook-owned maintenance operations. Put the global
        # override before the subcommand so they remain callable under a
        # user's restrictive mode without weakening any other hook query.
        maintenance_override = ["--override-mode"] if args and args[0] in {"verify", "index"} else []
        proc = subprocess.run(
            ["roam", *maintenance_override, "--json", *args],
            capture_output=True, text=True, timeout=timeout,
            env=env,
        )
        if not proc.stdout.strip():
            return None
        envelope = json.loads(proc.stdout)
        if not isinstance(envelope, dict):
            return None
        # Bind structured evidence to the process outcome. Without this, a
        # stale or malformed wrapper could print PASS while exiting with the
        # gate-failure code (or print FAIL while exiting zero), and the Stop
        # hook would trust only whichever half looked convenient.
        envelope["_hook_process_returncode"] = proc.returncode
        return envelope
    except Exception:
        return None


def _verify_protocol_state(envelope, expected_receipt):
    """Classify required Verify evidence as one closed protocol transaction."""
    if not isinstance(envelope, dict) or envelope.get("command") != "verify":
        return "unavailable"
    summary = envelope.get("summary")
    if not isinstance(summary, dict):
        return "unavailable"
    verdict = str(summary.get("verdict") or "").strip().upper().split(":", 1)[0].split(None, 1)[0]
    issue_count = summary.get("violation_count")
    files_checked = summary.get("files_checked")
    targets_checked = summary.get("targets_checked")
    violations = envelope.get("violations")
    returncode = envelope.get("_hook_process_returncode")
    receipt = summary.get("verification_receipt")
    if verdict not in {"PASS", "WARN", "FAIL"}:
        return "unavailable"
    if type(issue_count) is not int or issue_count < 0:
        return "unavailable"
    if type(files_checked) is not int or files_checked < 0:
        return "unavailable"
    if type(targets_checked) is not int or targets_checked < 0:
        return "unavailable"
    if not isinstance(violations, list) or len(violations) != issue_count:
        return "unavailable"
    if any(not isinstance(item, dict) for item in violations):
        return "unavailable"
    category_findings = []
    categories = envelope.get("categories")
    if categories is not None:
        if not isinstance(categories, dict):
            return "unavailable"
        for result in categories.values():
            if not isinstance(result, dict):
                return "unavailable"
            nested = result.get("violations", [])
            if not isinstance(nested, list) or any(not isinstance(item, dict) for item in nested):
                return "unavailable"
            category_findings.extend(nested)
    evidence_findings = violations + category_findings
    if not isinstance(returncode, int):
        return "unavailable"
    if summary.get("verification_complete") is not True or summary.get("partial_success") is not False:
        return "incomplete"
    if not isinstance(receipt, dict) or not isinstance(expected_receipt, dict):
        return "unavailable"
    if (
        receipt.get("schema") != "roam.verify.receipt.v3"
        or receipt.get("request_nonce") != expected_receipt.get("request_nonce")
        or receipt.get("scope_sha256") != expected_receipt.get("scope_sha256")
        or receipt.get("content_sha256") != expected_receipt.get("content_sha256")
        or receipt.get("content_sha256_before") != expected_receipt.get("content_sha256")
        or receipt.get("content_sha256_after") != expected_receipt.get("content_sha256")
        or receipt.get("target_file_count") != expected_receipt.get("target_file_count")
        or receipt.get("scope_stable") is not True
        or receipt.get("request_match") is not True
        or targets_checked != expected_receipt.get("target_file_count")
    ):
        return "unavailable"
    has_fail_finding = any(
        str(item.get("severity") or "").upper() == "FAIL"
        for item in evidence_findings
    )
    if verdict == "PASS":
        if returncode != 0 or has_fail_finding:
            return "unavailable"
        # Verify intentionally keeps advisory detector findings outside its
        # gate verdict. A complete rc0 PASS may therefore carry WARN rows, but
        # only from the closed advisory category set; any other contradiction
        # is malformed evidence and can never be treated as a pass.
        if any(
            str(item.get("severity") or "").upper() != "WARN"
            or str(item.get("category") or "") not in _ADVISORY_CATEGORIES
            for item in evidence_findings
        ):
            return "unavailable"
        return "passed"
    if verdict == "WARN":
        if returncode != 0 or has_fail_finding:
            return "unavailable"
        return "failed"
    if returncode != 5:
        return "unavailable"
    return "failed"


def _run_roam_stdin(args, stdin_text, timeout):
    """Like _run_roam but pipes a diff to the command's stdin (e.g.
    `git diff | roam critique`). Returns the parsed envelope or None. Fail-open."""
    try:
        proc = subprocess.run(
            ["roam", "--json", *args], input=stdin_text,
            capture_output=True, text=True, timeout=timeout,
        )
        if not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)
    except Exception:
        return None


def _git_diff_head():
    """Working-tree diff vs HEAD for the optional critique reviewer only."""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD"], capture_output=True, text=True,
            timeout=_GITDIFF_TIMEOUT_S,
        )
        return proc.stdout if proc.returncode == 0 else ""
    except Exception:
        return ""


def _log_stop_event(
    blocked,
    findings_n,
    advisory_n,
    verify_ms,
    skipped_no_edit,
    *,
    episode_event=None,
):
    """Best-effort block-rate telemetry: one counts-only JSON line per
    Stop-hook decision appended to `.roam/hook-stops.jsonl` (same dir
    convention as `.roam/compile-runs.jsonl`: cwd-relative, skip when
    `.roam/` doesn't exist, never grow past 10 MB). decision:block outcomes
    are the only place the compile stack spends real model tokens (each
    block = one extra full agent turn), so the block rate must be
    measurable. Finding TEXT stays out of the log (privacy) -- counts only.
    Never breaks the hook."""
    try:
        log_dir = os.path.join(os.getcwd(), ".roam")
        if not os.path.isdir(log_dir):
            return
        log_path = os.path.join(log_dir, "hook-stops.jsonl")
        if os.path.exists(log_path) and os.path.getsize(log_path) > 10 * 1024 * 1024:
            return  # rotate manually; never grow unbounded
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "blocked": bool(blocked),
            "findings": int(findings_n),
            "advisory_findings": int(advisory_n),
            "verify_ms": int(verify_ms),
            "skipped_no_edit": bool(skipped_no_edit),
            "episode_id": str((episode_event or {}).get("episode_id") or ""),
            "session_id": str((episode_event or {}).get("session_id") or ""),
            "turn_seq": (episode_event or {}).get("turn_seq"),
            "outcome": str((episode_event or {}).get("outcome") or ""),
            "terminal": bool((episode_event or {}).get("terminal")),
            "changed_files": (episode_event or {}).get("changed_files"),
            "diff_sha256": str((episode_event or {}).get("diff_sha256") or ""),
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + chr(10))  # chr(10): the enclosing
            # module embeds this script in a non-raw string literal
    except Exception:
        pass  # telemetry must never break the hook


def _collect_findings(d):
    """Prefer the flat, severity-sorted top-level `violations` list (verify
    already ranks FAIL first, then by blast radius); fall back to the
    per-category lists for older verify envelopes."""
    flat = d.get("violations")
    if isinstance(flat, list) and flat:
        return list(flat)
    out = []
    for _cat, res in (d.get("categories") or {}).items():
        out.extend((res or {}).get("violations") or [])
    return out


def _fmt(v):
    loc = f"{v.get('file')}:{v.get('line')}" if v.get("line") else str(v.get("file"))
    head = f"  - [{v.get('severity') or '?'}/{v.get('category')}] {loc} -- {v.get('message')}"
    if v.get("fix"):
        return [head, f"      fix: {v['fix']}"]
    return [head]


def _test_fail_targets(findings):
    """Test files of impacted-test FAILures (dedup, order-preserving)."""
    targets = []
    for v in findings:
        if v.get("category") != "tests":
            continue
        if v.get("severity") == "FAIL" or "FAILED" in str(v.get("message") or ""):
            f = v.get("file")
            if f and f not in targets:
                targets.append(f)
    return targets


def _whyfail_lines(targets):
    """Attach roam why-fail's root-cause frame for each failing test file."""
    body = []
    for tgt in targets[:_MAX_WHYFAIL_TESTS]:
        d = _run_roam(["why-fail", tgt], _WHYFAIL_TIMEOUT_S)
        if not d:
            continue
        suspects = d.get("suspects") or []
        if not suspects:
            continue
        verdict = str((d.get("summary") or {}).get("verdict") or "")
        body.append(f"  why-fail {tgt}: {verdict}")
        for s in suspects[:_MAX_WHYFAIL_SUSPECTS]:
            body.append(f"      suspect: {s.get('name')} ({s.get('kind')}) in {s.get('file') or '?'}")
        top = suspects[0].get("name")
        if top:
            body.append(f"      deeper root cause: roam diagnose {top}")
    if body:
        body.insert(0, "WHY-FAIL (recently-changed symbols the failing test reaches -- start the fix here):")
    return body


def _has_signature_change(findings):
    for v in findings:
        if str(v.get("category") or "").lower() in _SIGCHANGE_CATS:
            return True
        msg = str(v.get("message") or "").lower()
        if "signature" in msg or "breaking change" in msg:
            return True
    return False


def _critique_lines():
    """roam critique: patch-vs-graph second opinion on the diff (F2).
    Reads the unified diff from stdin; medium+ findings only."""
    diff = _git_diff_head()
    if not diff.strip():
        return []
    d = _run_roam_stdin(["critique"], diff, _CRITIQUE_TIMEOUT_S)
    if not d:
        return []
    notable = [f for f in (d.get("findings") or [])
               if _SEV_RANK.get(str(f.get("severity") or "").lower(), 0) >= 2]
    if not notable:
        return []
    out = [f"  critique ({len(notable)} finding(s) -- patch vs graph: "
           "clones-to-co-edit + blast radius):"]
    for f in notable[:_MAX_CRITIQUE_SHOWN]:
        out.append(f"      [{str(f.get('severity') or '?').upper()}/{f.get('check')}] {f.get('title')}")
    if len(notable) > _MAX_CRITIQUE_SHOWN:
        out.append(f"      ... and {len(notable) - _MAX_CRITIQUE_SHOWN} more")
    return out


def _prrisk_lines():
    """roam pr-risk: 0-100 diff risk score; warn only on high/critical (F19)."""
    d = _run_roam(["pr-risk"], _PRRISK_TIMEOUT_S)
    if not d:
        return []
    s = d.get("summary") or {}
    try:
        rank = int(s.get("risk_rank"))
    except (TypeError, ValueError):
        rank = 0
    if rank < _PRRISK_WARN_RANK:
        return []
    level = s.get("risk_level_canonical") or s.get("risk_level") or "?"
    return [f"  pr-risk: score {s.get('risk_score')}/100 ({level}) -- blast x "
            "hotspot x bus-factor x coupling; review the blast radius before finishing."]


def _adversarial_lines():
    """roam adversarial: high+ architecture challenges on the change (F19)."""
    d = _run_roam(["adversarial", "--severity", "high"], _ADVERSARIAL_TIMEOUT_S)
    if not d:
        return []
    challenges = d.get("challenges") or []
    if not challenges:
        return []
    out = [f"  adversarial ({len(challenges)} architecture challenge(s) at high+):"]
    for c in challenges[:_MAX_ADVERSARIAL_SHOWN]:
        out.append(f"      [{str(c.get('severity') or '?').upper()}/{c.get('type')}] {c.get('title')}")
    if len(challenges) > _MAX_ADVERSARIAL_SHOWN:
        out.append(f"      ... and {len(challenges) - _MAX_ADVERSARIAL_SHOWN} more")
    return out


def _vibe_lines():
    """roam vibe-check: repo-level AI-rot score, thresholded (F23)."""
    d = _run_roam(["vibe-check"], _VIBE_TIMEOUT_S)
    if not d:
        return []
    s = d.get("summary") or {}
    score = s.get("ai_rot_score")
    if score is None:
        score = s.get("score")
    try:
        score = int(score)
    except (TypeError, ValueError):
        return []
    try:
        thr = int(os.environ.get("ROAM_HOOK_VIBE_THRESHOLD", "50") or "50")
    except ValueError:
        thr = 50
    if score < thr:
        return []
    return [f"  vibe-check: AI-rot score {score}/100 (>= {thr}, repo-level) -- "
            "run `roam vibe-check` for the rot inventory."]


def _second_opinion_lines():
    """Run the opt-in second-opinion reviewers (all default-OFF, fail-open,
    silent-when-clean). Each reuses an existing roam command and runs
    independently of the verify verdict. Returns [] when none are enabled
    or none have anything to say (so the default hook stays byte-identical)."""
    out = []
    if _env_on("ROAM_HOOK_CRITIQUE", "0"):
        out.extend(_critique_lines())
    if _env_on("ROAM_HOOK_PRRISK", "0"):
        out.extend(_prrisk_lines())
    if _env_on("ROAM_HOOK_ADVERSARIAL", "0"):
        out.extend(_adversarial_lines())
    if _env_on("ROAM_HOOK_VIBE", "0"):
        out.extend(_vibe_lines())
    return out


def main():
    try:
        payload = json.load(sys.stdin)
        active = _active_episode(payload)
        root = _hook_repo_root()
        security_issue = None
        policy_before, policy_before_complete = _policy_snapshot(root)
        if active.get("evidence_required"):
            if active.get("evidence_error"):
                security_issue = "policy_evidence_unavailable"
            elif (
                active.get("policy_complete") is not True
                or not isinstance(active.get("policy_sha256"), str)
                or len(active.get("policy_sha256")) != 64
                or not policy_before_complete
            ):
                security_issue = "policy_evidence_unavailable"
            elif active.get("policy_sha256") != policy_before:
                security_issue = "policy_tampering"
        elif not policy_before_complete:
            # Standalone/manual Stop invocations have no prompt episode to
            # compare against, but still require a complete pre-Verify policy
            # snapshot and protect it across the verification transaction.
            security_issue = "policy_evidence_unavailable"

        snapshot = None
        snapshot_error = None
        if security_issue is None:
            snapshot, snapshot_error = _verification_snapshot(root, active)
            if snapshot_error:
                security_issue = "verification_snapshot_unavailable"
        skipped_no_edit = bool(snapshot is not None and not snapshot["paths"] and security_issue is None)
        diff_identity = {
            "changed_files": snapshot.get("target_file_count") if snapshot else None,
            "diff_sha256": snapshot.get("content_sha256") if snapshot else "",
        }
        verify_ms = 0
        d = None
        expected_receipt = None
        if not skipped_no_edit and security_issue is None:
            nonce = secrets.token_hex(16)
            expected_receipt = {
                "schema": "roam.verify.receipt.v3",
                "request_nonce": nonce,
                "scope_sha256": snapshot["scope_sha256"],
                "content_sha256": snapshot["content_sha256"],
                "content_sha256_before": snapshot["content_sha256"],
                "content_sha256_after": snapshot["content_sha256"],
                "target_file_count": snapshot["target_file_count"],
                "scope_stable": True,
                "request_match": True,
            }
            verify_env = {**os.environ, **_ADVISORY_ENV}
            verify_env.update({
                "ROAM_VERIFY_REQUEST_NONCE": nonce,
                "ROAM_VERIFY_SCOPE_SHA256": snapshot["scope_sha256"],
                "ROAM_VERIFY_CONTENT_SHA256": snapshot["content_sha256"],
                "ROAM_VERIFY_SCOPE_COUNT": str(snapshot["target_file_count"]),
            })
            verify_t0 = time.perf_counter()
            d = _run_roam(
                ["verify", "--auto", "--diff-only", "--", *snapshot["paths"]],
                _VERIFY_TIMEOUT_S,
                env=verify_env,
            )
            verify_ms = int((time.perf_counter() - verify_t0) * 1000)
            post_snapshot, post_error = _verification_snapshot(root, active)
            policy_after, policy_after_complete = _policy_snapshot(root)
            if not policy_after_complete or policy_after != policy_before:
                security_issue = "policy_tampering"
            elif post_error or not _same_verification_snapshot(snapshot, post_snapshot):
                security_issue = "verification_race"
        summary = (d or {}).get("summary") or {}
        verdict = str(summary.get("verdict") or "")
        verify_state = (
            "skipped"
            if skipped_no_edit
            else _verify_protocol_state(d, expected_receipt)
            if security_issue is None
            else "unavailable"
        )
        verify_failed = verify_state == "failed"
        verify_unavailable = security_issue is not None or verify_state in {"unavailable", "incomplete"}
        findings = _collect_findings(d) if d else []
        # BUG#62: advisory detectors (default-ON here) emit WARN-only
        # findings that never enter the verdict. Route them out of the
        # blocking set and surface them as a NON-BLOCKING transcript notice
        # (stderr) even on PASS -- never a decision:block.
        advisory = [
            v for v in findings
            if v.get("category") in _ADVISORY_CATEGORIES
            and str(v.get("severity") or "").upper() == "WARN"
        ]
        advisory_ids = {id(v) for v in advisory}
        findings = [v for v in findings if id(v) not in advisory_ids]
        if advisory:
            notice = [f"roam verify advisory (non-blocking, episode scope): {len(advisory)} finding(s)"]
            for v in advisory[:_MAX_OTHER_SHOWN]:
                notice.extend(_fmt(v))
            if len(advisory) > _MAX_OTHER_SHOWN:
                notice.append(f"  ... and {len(advisory) - _MAX_OTHER_SHOWN} more")
            notice.append("  (advisory only -- review now; change suppressions only in a separate approved episode)")
            print(chr(10).join(notice), file=sys.stderr)

        # Optional reviewers run inside the same transaction. A final exact
        # snapshot below catches any reviewer or concurrent agent mutation.
        extra = _second_opinion_lines() if security_issue is None else []
        if security_issue is None:
            final_snapshot, final_error = _verification_snapshot(root, active)
            policy_final, policy_final_complete = _policy_snapshot(root)
            if not policy_final_complete or policy_final != policy_before:
                security_issue = "policy_tampering"
            elif final_error or not _same_verification_snapshot(snapshot, final_snapshot):
                security_issue = "verification_race"
            if security_issue is not None:
                verify_unavailable = True

        if not skipped_no_edit and security_issue is None:
            # Run only after the exact verification transaction has closed.
            # The refresh writes internal `.roam/` state, excluded from source
            # scope, and can no longer race the evidence used for this stop.
            _maybe_refresh_whole_repo_report()

        lines = []
        if security_issue == "policy_tampering":
            lines.extend([
                "BLOCKING [policy_tampering]: Verify policy, suppression, baseline, hook, or Claude settings changed during this episode.",
                "Restore the prompt-start policy state. Make policy changes only in a separate user-approved episode; they cannot satisfy this stop.",
            ])
        elif security_issue == "policy_evidence_unavailable":
            lines.extend([
                "BLOCKING [policy_evidence_unavailable]: the protected prompt-start policy snapshot is missing or incomplete.",
                "Start a fresh Claude turn with the current roam hooks installed, then rerun Verify before stopping.",
            ])
        elif security_issue == "verification_race":
            lines.extend([
                "BLOCKING [verification_race]: filenames, bytes, Git status, or HEAD changed while post-edit evidence was being produced.",
                "Stop concurrent edits and rerun the automatically bound Verify transaction on the final bytes.",
            ])
        elif security_issue == "verification_snapshot_unavailable":
            lines.extend([
                "BLOCKING [verification_snapshot_unavailable]: the exact episode filename/content snapshot could not be proven "
                f"({snapshot_error or 'unknown_snapshot_error'}).",
                "Restore readable regular files and Git status, then rerun Verify before stopping.",
            ])
        elif verify_unavailable:
            lines.extend([
                "roam verify could not produce complete post-edit evidence (receipt v3 required).",
                "BLOCKING: keep this edit open; run `roam verify --auto --diff-only` "
                "successfully before stopping. Do not bypass the gate with policy, "
                "baseline, or suppression edits.",
            ])
        elif verify_failed and findings:
            lines.append(f"roam verify (post-edit, prompt-base episode scope): {verdict}")

            if _env_on("ROAM_HOOK_PROMINENT", "1"):
                # Partition so BLOCK-level (FAIL) findings -- failed tests,
                # hallucinated imports, breaking changes -- are shown first and
                # never truncated away behind style WARNs.
                fails = [v for v in findings if v.get("severity") == "FAIL"]
                rest = [v for v in findings if v.get("severity") != "FAIL"]
                if fails:
                    lines.append(f"BLOCKING -- {len(fails)} must-fix finding(s):")
                    for v in fails[:_MAX_FAIL_SHOWN]:
                        lines.extend(_fmt(v))
                    if len(fails) > _MAX_FAIL_SHOWN:
                        lines.append(f"  ... and {len(fails) - _MAX_FAIL_SHOWN} more blocking")
                if rest:
                    lines.append(f"OTHER -- {len(rest)} finding(s):")
                    for v in rest[:_MAX_OTHER_SHOWN]:
                        lines.extend(_fmt(v))
                    if len(rest) > _MAX_OTHER_SHOWN:
                        lines.append(f"  ... and {len(rest) - _MAX_OTHER_SHOWN} more")
            else:
                for v in findings[:8]:
                    lines.extend(_fmt(v))
                if len(findings) > 8:
                    lines.append(f"  ... and {len(findings) - 8} more")

            if _env_on("ROAM_HOOK_WHYFAIL", "1"):
                targets = _test_fail_targets(findings)
                if targets:
                    lines.extend(_whyfail_lines(targets))

            if _env_on("ROAM_HOOK_DOCDRIFT", "0") and _has_signature_change(findings):
                lines.append(
                    "DOC-DRIFT (advisory): a public signature changed -- docs/README "
                    "may be stale. Reuse: `roam doc-staleness` / `roam api-drift`."
                )

            # AUTO-FIX directive -- on by default. The block makes the agent
            # resolve findings on lines it just touched instead of stopping;
            # every continuation re-runs Verify, while Claude Code's own
            # consecutive-block cap provides the loop bound.
            lines.append(
                "AUTO-FIX: resolve these now. EDIT the file(s) to fix each "
                "finding on a line your change touched. Do not edit Verify "
                "configuration, baselines, or suppressions during automatic "
                "correction; report a genuine false positive to the user. Only "
                "clearly pre-existing, unrelated findings may be left. Verify "
                "re-runs automatically after your fix."
            )
        elif verify_failed:
            lines.extend([
                f"roam verify failed without actionable findings: {verdict}",
                "BLOCKING: run `roam verify --auto --diff-only --verbose`, repair "
                "the gate failure, and rerun Verify before stopping.",
            ])

        # Opt-in second-opinion reviewers are advisory, but their execution was
        # included inside the final byte/status comparison above.
        if extra:
            if lines:
                lines.append("")
            lines.append(
                "SECOND OPINION (opt-in roam reviewers -- advisory; address or "
                "justify, they do not auto-block):"
            )
            lines.extend(extra)

        blocked = bool(lines)
        if security_issue is not None:
            outcome = security_issue
        elif skipped_no_edit:
            outcome = "no_edit"
        elif blocked and verify_unavailable:
            outcome = "verify_unavailable"
        elif blocked and verify_failed and findings:
            outcome = "verification_blocked"
        elif blocked and verify_failed:
            outcome = "verification_failed_without_findings"
        elif blocked:
            outcome = "second_opinion_blocked"
        elif verify_failed:
            outcome = "verification_failed_without_findings"
        else:
            outcome = "verified_clean"
        episode_event = _record_episode_stop(
            payload,
            active,
            outcome,
            not blocked,
            blocked,
            verify_ms,
            skipped_no_edit,
            diff_identity,
        )
        _log_stop_event(
            blocked,
            len(findings),
            len(advisory),
            verify_ms,
            skipped_no_edit,
            episode_event=episode_event,
        )
        if not lines:
            return  # quiet: clean verify and nothing from any enabled reviewer
        print(json.dumps({"decision": "block", "reason": chr(10).join(lines)}))
    except Exception:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "roam verify Stop hook could not validate this stop. "
                "Run `roam verify --auto --diff-only` successfully before stopping."
            ),
        }))


main()
