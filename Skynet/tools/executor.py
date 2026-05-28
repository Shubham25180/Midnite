"""Execute tool calls from the LLM and return string results."""
from __future__ import annotations

import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.task.task_router import TaskRouter
    from Skynet.core.runtime_manager import RuntimeManager

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(".")
_TASK_ROUTER: "TaskRouter | None" = None
_MANAGER: "RuntimeManager | None" = None


def register(task_router: "TaskRouter", manager: "RuntimeManager") -> None:
    """Wire executor to live runtime objects (called from main)."""
    global _TASK_ROUTER, _MANAGER
    _TASK_ROUTER = task_router
    _MANAGER = manager


def execute(name: str, arguments: dict) -> str:
    """Dispatch a tool call by name. Always returns a string."""
    logger.info("Tool call: %s(%s)", name, list(arguments.keys()))
    try:
        match name:
            case "read_file":
                return _read_file(arguments.get("path", ""))
            case "write_file":
                return _write_file(arguments.get("path", ""), arguments.get("content", ""))
            case "list_files":
                return _list_files(arguments.get("directory", "."))
            case "run_bash":
                return _run_bash(arguments.get("command", ""))
            case "get_system_info":
                return _get_system_info()
            case "reload_skills":
                return _reload_skills()
            case "read_all_files":
                return _read_all_files(arguments.get("directory", "."), int(arguments.get("max_files", 12)))
            case "glob_files":
                return _glob_files(arguments.get("pattern", "**/*"))
            case "grep_files":
                return _grep_files(
                    arguments.get("pattern", ""),
                    arguments.get("path", "."),
                    arguments.get("file_glob", ""),
                )
            case "edit_file":
                return _edit_file(
                    arguments.get("path", ""),
                    arguments.get("old_string", ""),
                    arguments.get("new_string", ""),
                )
            case "multi_edit_file":
                return _multi_edit_file(arguments.get("path", ""), arguments.get("edits", []))
            case "web_fetch":
                return _web_fetch(arguments.get("url", ""), arguments.get("prompt", ""))
            case "get_recent_history":
                return _get_recent_history(int(arguments.get("n_turns", 10)))
            case "save_memory":
                return _save_memory(arguments.get("text", ""), arguments.get("importance", "important"))
            case "search_memory":
                return _search_memory(arguments.get("query", ""))
            case "load_skill":
                return _load_skill(arguments.get("name", ""))
            case "take_screenshot":
                from Skynet.tools.vision_tools import take_screenshot
                return take_screenshot(arguments.get("prompt", "Describe everything you see on screen in detail."))
            case "web_browse":
                from Skynet.tools.browser_tools import web_browse
                return web_browse(
                    arguments.get("url", ""),
                    arguments.get("selector", ""),
                    arguments.get("wait_for", ""),
                )
            case "read_pdf":
                from Skynet.tools.file_readers import read_pdf
                return read_pdf(
                    arguments.get("path", ""),
                    arguments.get("pages", "all"),
                    int(arguments.get("dpi", 200)),
                )
            case "read_spreadsheet":
                from Skynet.tools.file_readers import read_spreadsheet
                return read_spreadsheet(
                    arguments.get("path", ""),
                    arguments.get("sheet"),
                    int(arguments.get("max_rows", 100)),
                )
            case "read_word":
                from Skynet.tools.file_readers import read_word
                return read_word(arguments.get("path", ""))
            case "write_spreadsheet":
                from Skynet.tools.file_writers import write_spreadsheet
                return write_spreadsheet(
                    arguments.get("path", ""),
                    arguments.get("rows", []),
                    arguments.get("sheet", "Sheet1"),
                )
            case "write_word":
                from Skynet.tools.file_writers import write_word
                return write_word(
                    arguments.get("path", ""),
                    arguments.get("content", ""),
                )
            case "browser_action":
                from Skynet.tools.browser_tools import browser_action
                return browser_action(
                    action=arguments.get("action", ""),
                    url=arguments.get("url", ""),
                    selector=arguments.get("selector", ""),
                    text=arguments.get("text", ""),
                    role=arguments.get("role", ""),
                    value=arguments.get("value", ""),
                    wait_for=arguments.get("wait_for", ""),
                    timeout_ms=int(arguments.get("timeout_ms", 15_000)),
                )
            case _:
                return f"Unknown tool: {name}"
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return f"Tool error: {exc}"


# ── Tool implementations ───────────────────────────────────────────────────────

def _read_file(path: str) -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    if len(content) > 8000:
        return content[:8000] + f"\n... (truncated — {len(content)} total chars)"
    return content


def _write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info("write_file: %s  (%d chars)", path, len(content))
    return f"Written: {path}  ({len(content)} chars)"


def _list_files(directory: str) -> str:
    p = _safe_path(directory)
    if not p.exists():
        return f"Directory not found: {directory}"
    lines = []
    for item in sorted(p.iterdir()):
        tag = "[dir] " if item.is_dir() else "      "
        lines.append(f"{tag}{item.name}")
    return "\n".join(lines) if lines else "(empty)"


# Commands that can cause irreversible system damage — block and ask for confirmation
_DANGEROUS = re.compile(
    r"\b(rm\s+-[rf]{1,2}f?|Remove-Item\s+.*-Recurse.*-Force|rd\s+/s|del\s+/[sfq]"
    r"|format\s+[a-z]:?|mkfs|dd\s+if=|DROP\s+TABLE|DELETE\s+FROM\s"
    r"|shutdown|restart-computer|Stop-Computer|taskkill\s+/f"
    r"|net\s+user\s+\w+\s+/delete|reg\s+delete"
    r"|git\s+push\s+.*--force|git\s+reset\s+--hard|git\s+clean\s+-[fdx])\b",
    re.IGNORECASE,
)


def _run_bash(command: str) -> str:
    if _DANGEROUS.search(command):
        logger.warning("run_bash BLOCKED (dangerous): %s", command)
        return (
            f"BLOCKED: '{command}' is a potentially destructive command. "
            "Tell the user what you want to do and ask them to confirm before running it."
        )
    logger.info("run_bash: %s", command)
    # Use PowerShell on Windows for ls, ~, git, python etc.
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_PROJECT_ROOT.resolve()),
    )
    output = (result.stdout + result.stderr).strip()
    if len(output) > 4000:
        output = output[:4000] + "\n... (truncated)"
    return output or f"(exit {result.returncode}, no output)"


def _get_system_info() -> str:
    import platform, sys
    lines = ["Nexux system status:"]

    # Hardware + environment
    lines.append(f"\nEnvironment: {platform.system()} {platform.machine()}  Python {sys.version.split()[0]}")
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        lines.append(
            f"CPU: {cpu:.0f}%  RAM: {ram.used / 1024**3:.1f}/{ram.total / 1024**3:.1f} GB ({ram.percent:.0f}%)"
        )
        try:
            disk = psutil.disk_usage(".")
            lines.append(f"Disk: {disk.free / 1024**3:.1f} GB free / {disk.total / 1024**3:.1f} GB total")
        except Exception:
            pass
    except ImportError:
        lines.append("CPU/RAM: install psutil for live metrics")
    except Exception:
        pass

    # GPU
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            for line in r.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    name, util, mem_used, mem_total = parts[0], parts[1], parts[2], parts[3]
                    temp = f"  {parts[4]}°C" if len(parts) > 4 else ""
                    lines.append(f"GPU: {name}  util={util}%  VRAM={mem_used}/{mem_total} MB{temp}")
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Components
    if _MANAGER:
        lines.append("\nComponents:")
        for name, comp in _MANAGER._components.items():
            lines.append(f"  {name}: {comp.health().name}")

    if _TASK_ROUTER:
        index = _TASK_ROUTER.skill_index
        if index:
            lines.append("\nAvailable skills:")
            for entry in index:
                lines.append(f"  {entry['name']}: {entry.get('description', '')}")

    try:
        from Skynet.memory.vector_store import count as qdrant_count
        from Skynet.memory.session_store import load_recent_summaries
        sessions = load_recent_summaries(n=3)
        lines.append(f"\nMemory: {qdrant_count()} semantic entries, {len(sessions)} session summaries")
    except Exception:
        pass

    if _MANAGER:
        orc = _MANAGER.get_component("orchestrator")
        if orc and hasattr(orc, "_provider"):
            lines.append(f"\nLLM: {type(orc._provider).__name__}  model={getattr(orc._provider, 'model', '?')}")

    return "\n".join(lines)


def _reload_skills() -> str:
    if _TASK_ROUTER is None:
        return "TaskRouter not registered with executor"
    count = _TASK_ROUTER.reload_skills()
    return f"Skill index reloaded: {count} skills available"


def _read_all_files(directory: str, max_files: int = 12) -> str:
    p = _safe_path(directory)
    if not p.exists():
        return f"Directory not found: {directory}"
    if not p.is_dir():
        return f"Not a directory: {directory}"
    files = sorted(f for f in p.rglob("*") if f.is_file())[:max_files]
    if not files:
        return f"[EMPTY] No files found in '{directory}'"

    budget_per_file = max(1000, 6000 // len(files))
    root = _PROJECT_ROOT.resolve()

    def _read_one(f: Path) -> tuple[str, str]:
        rel = str(f.relative_to(root))
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            if len(content) > budget_per_file:
                content = content[:budget_per_file] + f"\n... (truncated — {len(content)} total)"
        except Exception as exc:
            content = f"[read error: {exc}]"
        return rel, content

    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(files))) as pool:
        futures = {pool.submit(_read_one, f): f for f in files}
        for fut in as_completed(futures):
            rel, content = fut.result()
            results[rel] = content

    parts: list[str] = [f"Reading {len(files)} files from '{directory}':\n"]
    total_chars = 0
    for rel in sorted(results):
        content = results[rel]
        parts.append(f"\n{'='*60}\nFILE: {rel}\n{'='*60}\n{content}")
        total_chars += len(content)
    parts.append(f"\n\n[Total: {len(files)} files, ~{total_chars} chars]")
    return "\n".join(parts)


# ── Glob / Grep / Edit / WebFetch ──────────────────────────────────────────────

_SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"})


def _glob_files(pattern: str) -> str:
    root = _PROJECT_ROOT.resolve()
    try:
        matches = sorted(
            p for p in root.glob(pattern)
            if not any(part in _SKIP_DIRS for part in p.parts)
        )
    except Exception as exc:
        return f"Glob error: {exc}"
    if not matches:
        return f"No files match pattern: {pattern}"
    lines = []
    for m in matches[:200]:
        rel = str(m.relative_to(root))
        tag = "[dir] " if m.is_dir() else "      "
        lines.append(f"{tag}{rel}")
    suffix = f"\n... ({len(matches) - 200} more)" if len(matches) > 200 else ""
    return "\n".join(lines) + suffix


def _grep_files(pattern: str, path: str = ".", file_glob: str = "") -> str:
    if not pattern:
        return "Pattern required."
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"Invalid regex: {exc}"

    root = _PROJECT_ROOT.resolve()
    search_root = _safe_path(path) if path != "." else root

    glob_pat = file_glob if file_glob else "**/*"
    try:
        candidates = [
            f for f in search_root.glob(glob_pat)
            if f.is_file() and not any(part in _SKIP_DIRS for part in f.parts)
        ]
    except Exception as exc:
        return f"Glob error during grep: {exc}"

    matches: list[str] = []

    def _search_file(f: Path) -> list[str]:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return []
        rel = str(f.relative_to(root))
        hits = []
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                hits.append(f"{rel}:{i}: {line.rstrip()}")
        return hits

    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(_search_file, candidates):
            matches.extend(result)
            if len(matches) >= 200:
                break

    if not matches:
        return f"No matches for pattern: {pattern}"
    suffix = f"\n... ({len(matches) - 200} more matches)" if len(matches) > 200 else ""
    return "\n".join(matches[:200]) + suffix


def _edit_file(path: str, old_string: str, new_string: str) -> str:
    if not path:
        return "path is required."
    if old_string == new_string:
        return "old_string and new_string are identical — nothing to do."
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    count = content.count(old_string)
    if count == 0:
        # Provide helpful context: nearby lines
        lines = content.splitlines()
        snippet = "\n".join(lines[:20]) if lines else "(file is empty)"
        return (
            f"old_string not found in '{path}'.\n"
            f"First 20 lines of file:\n{snippet}"
        )
    if count > 1:
        return (
            f"old_string appears {count} times in '{path}'. "
            "Provide more surrounding context to make it unique."
        )
    new_content = content.replace(old_string, new_string, 1)
    p.write_text(new_content, encoding="utf-8")
    logger.info("edit_file: %s  (1 replacement)", path)
    return f"Edited: {path}  (1 replacement, {abs(len(new_content) - len(content)):+d} chars)"


def _multi_edit_file(path: str, edits: list) -> str:
    if not path:
        return "path is required."
    if not edits:
        return "No edits provided."
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    applied = 0
    errors: list[str] = []
    for i, edit in enumerate(edits):
        old = edit.get("old_string", "")
        new = edit.get("new_string", "")
        if not old:
            errors.append(f"Edit #{i+1}: old_string is empty")
            continue
        count = content.count(old)
        if count == 0:
            errors.append(f"Edit #{i+1}: old_string not found")
            continue
        if count > 1:
            errors.append(f"Edit #{i+1}: old_string is ambiguous ({count} matches)")
            continue
        content = content.replace(old, new, 1)
        applied += 1
    if applied > 0:
        p.write_text(content, encoding="utf-8")
        logger.info("multi_edit_file: %s  (%d edits)", path, applied)
    result = f"Applied {applied}/{len(edits)} edits to '{path}'."
    if errors:
        result += "\nErrors:\n" + "\n".join(f"  {e}" for e in errors)
    return result


def _web_fetch(url: str, prompt: str = "") -> str:
    if not url:
        return "url is required."
    if not url.startswith(("http://", "https://")):
        return f"Invalid URL (must start with http:// or https://): {url}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Nexux/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(200_000).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Fetch error: {exc}"

    # Strip HTML tags to plain text
    text = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) > 8000:
        text = text[:8000] + f"\n... (truncated — {len(text)} total chars)"

    if prompt:
        return f"[URL: {url}]\n[Prompt: {prompt}]\n\n{text}"
    return f"[URL: {url}]\n\n{text}"


def _get_recent_history(n_turns: int = 10) -> str:
    from Skynet.memory.raw_log import read_today
    n_turns = min(max(1, n_turns), 50)
    entries = read_today(limit=n_turns * 2)  # each turn = user + assistant
    if not entries:
        return "No conversation history found for today's session."
    lines = []
    for e in entries:
        role = e.get("role", "?").upper()
        content = e.get("content", "")[:300]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _save_memory(text: str, importance: str = "important") -> str:
    if not text.strip():
        return "Nothing to save."
    from Skynet.memory.vector_store import store
    valid = {"core", "important", "summary"}
    entry_type = importance if importance in valid else "important"
    store(text, entry_type=entry_type)
    logger.info("Memory saved (%s): %d chars", entry_type, len(text))
    return f"Saved to memory ({entry_type}): {text[:120]}{'...' if len(text) > 120 else ''}"


def _search_memory(query: str) -> str:
    from Skynet.memory.vector_store import search
    from Skynet.memory.session_store import load_recent_summaries
    results: list[str] = []
    # Core memories always returned first (regardless of score)
    core_hits = search(query, top_k=5, entry_type="core")
    if core_hits:
        results.append("Core memories (never forget):")
        for h in core_hits:
            text = h["meta"].get("text", "")
            ts = h["meta"].get("ts", "")[:10]
            if text:
                results.append(f"  [core {ts}] {text}")
    # Semantic search across all types
    hits = search(query, top_k=5)
    non_core = [h for h in hits if h["meta"].get("type") != "core"]
    if non_core:
        results.append("Relevant memory:")
        for h in non_core:
            text = h["meta"].get("text", "")
            ts = h["meta"].get("ts", "")[:10]
            kind = h["meta"].get("type", "?")
            score = h.get("score", 0)
            if text:
                results.append(f"  [{kind} {ts}] {text}  (score={score:.2f})")
    # Recent session summaries from SQLite
    sessions = load_recent_summaries(n=3)
    if sessions:
        results.append("Recent sessions:")
        for s in reversed(sessions):
            results.append(f"  [{s['ts'][:10]}] {s['summary']}")
            if s["facts"]:
                fact_strs = [
                    next(iter(f.values())) if isinstance(f, dict) else str(f)
                    for f in s["facts"]
                ]
                results.append("  Facts: " + "; ".join(fact_strs))
    return "\n".join(results) if results else "No memories found yet."


def _load_skill(name: str) -> str:
    from pathlib import Path
    import yaml
    skill_path = Path("config/skills") / f"{name}.yaml"
    if not skill_path.exists():
        available = [p.stem for p in Path("config/skills").glob("*.yaml") if p.stem != "index"]
        return f"Skill '{name}' not found. Available: {', '.join(available) or 'none'}"
    with open(skill_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    instructions = data.get("instructions", "No instructions found.")
    return f"Skill '{name}' loaded. Follow these instructions:\n{instructions}"


# ── Safety ─────────────────────────────────────────────────────────────────────

def _safe_path(path: str) -> Path:
    import difflib
    root = _PROJECT_ROOT.resolve()
    p = Path(path)
    # If absolute, try stripping a prefix that looks like the project root (handles typos)
    if p.is_absolute():
        try:
            rel = p.relative_to(root)
            return (root / rel).resolve()
        except ValueError:
            pass
        # Fuzzy: check if any part of the path after stripping drive/root matches a real subpath
        parts = p.parts[1:]  # skip drive letter or leading /
        candidates = [str(root / Path(*parts[i:])) for i in range(min(len(parts), 3))]
        for c in candidates:
            cp = Path(c).resolve()
            if str(cp).startswith(str(root)) and cp.exists():
                return cp
        # Last resort: suggest a relative path from directory names
        dir_name = p.name or (p.parts[-1] if p.parts else path)
        matches = difflib.get_close_matches(dir_name, [x.name for x in root.rglob("*") if x.is_dir()], n=1, cutoff=0.6)
        hint = f" Did you mean '{matches[0]}/'?" if matches else " Use relative paths like 'docs/' or 'Skynet/core/'."
        raise ValueError(f"Path outside project root: '{path}'.{hint}")
    resolved = (root / path).resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path outside project root: '{path}'. Use relative paths like 'docs/' or 'Skynet/core/'.")
    return resolved
