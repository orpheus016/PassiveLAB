#!/usr/bin/env python3
# roam-hook-version: 15
"""roam compile -> Claude Code UserPromptSubmit context injection.

Installed by `roam hooks claude --write`. FAIL-OPEN: any error prints
nothing and exits 0 (a broken roam install must never block a turn).
"""
import json
import hashlib
import os
import stat
import subprocess
import sys
import time

_COMPILE_TIMEOUT_S = 6.0
_MIN_PROMPT_CHARS = 8
_EPISODE_SCHEMA = 1
_LOCK_ATTEMPTS = 20
_LOCK_SLEEP_S = 0.005
_LOCK_STALE_S = 30.0
# S2-lite warm daemon: startup dominates this chain (~346 ms cold vs ~2 ms
# envelope compute on a cache hit), so try the loopback daemon first. The
# connect budget is tiny on purpose: an absent daemon must cost ~nothing.
_DAEMON_CONNECT_TIMEOUT_S = 0.01
_POLICY_MAX_FILE_BYTES = 4 * 1024 * 1024
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


def _repo_root():
    d = os.getcwd()
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.getcwd()
        d = parent


def _evidence_base(root, create):
    """Return a restrictive state directory that is never inside the repo."""
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


def _episode_state_path(root, session_key, create):
    base = _evidence_base(root, create)
    if not base:
        return ""
    repo_key = hashlib.sha256(os.path.normcase(os.path.realpath(root)).encode("utf-8", "replace")).hexdigest()[:24]
    state_root = os.path.join(base, repo_key)
    try:
        if create:
            os.makedirs(state_root, mode=0o700, exist_ok=True)
            if os.name != "nt":
                os.chmod(state_root, 0o700)
        if not os.path.isdir(state_root):
            return ""
        return os.path.join(state_root, session_key + ".json")
    except OSError:
        return ""


def _git_base_head(root):
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=root,
            capture_output=True, text=True, timeout=10,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return "", "unavailable"
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=root,
            capture_output=True, text=True, timeout=10,
        )
        if head.returncode != 0:
            return "", "unborn"
        value = head.stdout.strip().lower()
        if len(value) not in (40, 64) or any(ch not in "0123456789abcdef" for ch in value):
            return "", "unavailable"
        return value, "present"
    except Exception:
        return "", "unavailable"


def _same_file_state(left, right, cross_handle=False):
    fields = ["st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"]
    if cross_handle and os.name == "nt":
        fields.remove("st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _policy_file_state(path):
    """Hash one policy file without following repo-controlled symlinks."""
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


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _session_key(payload):
    session_id = str(payload.get("session_id") or "").strip()
    transcript_path = str(payload.get("transcript_path") or "").strip()
    stable = session_id or transcript_path
    if not stable:
        return "", session_id, transcript_path
    return hashlib.sha256(stable.encode("utf-8", "replace")).hexdigest()[:24], session_id, transcript_path


def _acquire_lock(path):
    for _ in range(_LOCK_ATTEMPTS):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode("ascii", "replace"))
            return fd
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > _LOCK_STALE_S:
                    os.unlink(path)
                    continue
            except OSError:
                pass
            time.sleep(_LOCK_SLEEP_S)
        except OSError:
            return None
    return None


def _release_lock(path, fd):
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


def _atomic_json(path, value):
    tmp = path + ".tmp-%d-%d" % (os.getpid(), time.time_ns())
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, sort_keys=True, separators=(",", ":"))
            fh.write(chr(10))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _append_episode_event(root, event):
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
    fd = _acquire_lock(lock_path)
    if fd is None:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + chr(10))
    finally:
        _release_lock(lock_path, fd)


def _start_episode(payload, prompt):
    root = _repo_root()
    session_key, session_id, transcript_path = _session_key(payload)
    if not session_key:
        return session_id, "", ""
    try:
        state_path = _episode_state_path(root, session_key, True)
        if not state_path:
            return session_id, "", ""
        lock_path = state_path + ".lock"
        fd = _acquire_lock(lock_path)
        if fd is None:
            return session_id, "", ""
        try:
            state = {}
            try:
                with open(state_path, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                    if isinstance(loaded, dict):
                        state = loaded
            except (OSError, ValueError):
                state = {}
            turn_seq = int(state.get("last_turn_seq") or 0) + 1
            started_at_ms = int(time.time() * 1000)
            prompt_hash = hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest()
            seed = "%s\0%d\0%s\0%d\0%d" % (
                session_key,
                turn_seq,
                prompt_hash,
                time.time_ns(),
                os.getpid(),
            )
            episode_id = "ep_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
            base_head, base_head_state = _git_base_head(root)
            policy_sha256, policy_complete = _policy_snapshot(root)
            state = {
                "state_schema": "roam.hook.episode.v2",
                "repo_sha256": hashlib.sha256(
                    os.path.normcase(os.path.realpath(root)).encode("utf-8", "replace")
                ).hexdigest(),
                "session_id": session_id,
                "last_turn_seq": turn_seq,
                "active": {
                    "episode_id": episode_id,
                    "started_at_ms": started_at_ms,
                    "turn_seq": turn_seq,
                    "base_head": base_head,
                    "base_head_state": base_head_state,
                    "policy_sha256": policy_sha256,
                    "policy_complete": bool(policy_complete),
                },
            }
            _atomic_json(state_path, state)
        finally:
            _release_lock(lock_path, fd)
        event = {
            "schema_version": _EPISODE_SCHEMA,
            "hook_version": 15,
            "evidence_source": "live_hook",
            "event_id": "evt_" + hashlib.sha256((episode_id + ":start").encode("utf-8")).hexdigest()[:24],
            "episode_id": episode_id,
            "event_type": "prompt_submitted",
            "ts": _utc_now(),
            "session_id": session_id,
            "turn_seq": turn_seq,
            "terminal": False,
            "outcome": "pending",
            "prompt_sha256": prompt_hash,
            "prompt_chars": len(prompt),
            "transcript_path_sha256": (
                hashlib.sha256(transcript_path.encode("utf-8", "replace")).hexdigest()
                if transcript_path
                else ""
            ),
            "permission_mode": str(payload.get("permission_mode") or ""),
            "compile_expected": len(prompt) >= _MIN_PROMPT_CHARS,
            "health_state": "unknown",
            "base_head": base_head,
            "base_head_state": base_head_state,
            "policy_snapshot_complete": bool(policy_complete),
        }
        _append_episode_event(root, event)
        return session_id, episode_id, str(turn_seq)
    except Exception:
        return session_id, "", ""


def _try_daemon(prompt, session_id, episode_id, turn_seq):
    """Compile via the repo's warm daemon; None on ANY failure (-> cold spawn)."""
    try:
        import socket
        cfg_path = os.path.join(_repo_root(), ".roam", "compile-daemon.json")
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        s = socket.create_connection(("127.0.0.1", int(cfg["port"])),
                                     timeout=_DAEMON_CONNECT_TIMEOUT_S)
        try:
            s.settimeout(_COMPILE_TIMEOUT_S)
            req = {"token": cfg.get("token"), "op": "compile",
                   "args": [prompt], "cwd": os.getcwd(),
                   "session_id": session_id,
                   "episode_id": episode_id,
                   "turn_seq": turn_seq}
            s.sendall((json.dumps(req) + chr(10)).encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                chunks.append(b)
        finally:
            s.close()
        d = json.loads(b"".join(chunks).decode("utf-8"))
        if not isinstance(d, dict) or d.get("error") or "summary" not in d:
            return None  # daemon refused (wrong repo / bad token) or junk
        return d
    except Exception:
        return None  # fail open into the cold spawn


def main():
    try:
        payload = json.load(sys.stdin)
        prompt = (payload.get("prompt") or "").strip()
        session_id, episode_id, turn_seq = _start_episode(payload, prompt)
        if len(prompt) < _MIN_PROMPT_CHARS:
            return
        # Forward hook correlation state to the compiler. The privacy boundary
        # persists only the opaque episode join key; session and turn values
        # remain transient inputs used by the hook lifecycle.
        d = _try_daemon(prompt, session_id, episode_id, turn_seq)
        if d is None:
            env = os.environ.copy()
            if session_id:
                env["ROAM_SESSION_ID"] = session_id
            if episode_id:
                env["ROAM_EPISODE_ID"] = episode_id
            if turn_seq:
                env["ROAM_TURN_SEQ"] = turn_seq
            # Stamp real hook traffic as 'hook' so it is distinguishable from the
            # mixed 'unknown' bucket in compile-stats. setdefault, not assign: an
            # explicit ROAM_AGENT_MODE (a policy mode the user set) is preserved.
            env.setdefault("ROAM_AGENT_MODE", "hook")
            # Resolve the compiler through the *running* interpreter, never a
            # bare "roam" off PATH. A stale global install shadowing the active
            # environment writes telemetry in an older row schema and skips the
            # owner-only state-directory install, which silently zeroes
            # `compile-stats` afterwards. Matches the house pattern used by
            # ask/runner, cmd_report, cmd_replay and mcp_server.
            proc = subprocess.run(
                [sys.executable, "-m", "roam", "--json", "compile", prompt],
                capture_output=True, text=True, timeout=_COMPILE_TIMEOUT_S,
                env=env,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return
            d = json.loads(proc.stdout)
        summary = d.get("summary") or {}
        # The obligation blocks ride SEPARATELY from the facts block. An
        # envelope can be skip-advised (facts not worth injecting) while
        # still being edit-context, and the obligations are exactly what
        # such a turn needs -- so they are read before the skip return.
        contract = d.get("execution_contract") or []
        review = (d.get("orchestration_contract") or {}).get("obligations") or []
        # Generation-shaped tasks (write a test / implement X): measured
        # net-negative to inject the FACTS -- the envelope is cache-re-read
        # every turn while the agent must read/edit/run regardless. The
        # measured result is about the facts payload, so the skip path emits
        # the obligations ALONE and never the full block; widening it here
        # would silently repeal that A/B.
        if str(summary.get("injection_advice") or "").startswith("skip"):
            if contract or review:
                _print_obligations(contract, review)
            return
        plan = (d.get("artifact") or {}).get("plan") or {}
        facts = {k: v for k, v in (plan.get("prefetched_facts") or {}).items()
                 if not k.startswith("_")}
        block = {
            "procedure": summary.get("procedure"),
            "confidence": summary.get("classifier_confidence"),
            "named_paths": (plan.get("named_paths") or [])[:6],
            "recommended_first": plan.get("recommended_first_command"),
            "answer_contract": plan.get("answer_contract"),
            "prefetched_facts": facts,
        }
        block = {k: v for k, v in block.items() if v}
        if not block:
            if contract or review:
                _print_obligations(contract, review)
            return
        print("PRE-COMPUTED PLAN (roam compile -- answer from these "
              "embedded facts; do not re-gather what is already answered):")
        print(json.dumps(block, ensure_ascii=False))
        if contract or review:
            _print_obligations(contract, review)
    except Exception:
        return  # fail open


def _print_obligations(contract, review):
    """Emit the phased-work and cross-family review obligations.

    Plain numbered lines, not JSON: these are instructions to the agent,
    while the facts block above is data for it to answer from.
    """
    print("EXECUTION CONTRACT (roam compile -- this turn edits code; "
          "these obligations are not optional):")
    for line in list(contract) + list(review):
        print("  " + str(line))


main()
