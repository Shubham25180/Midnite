"""Browser automation tools.

N1: web_browse     — headless JS-rendered page fetch (temp page per call)
N5: browser_action — persistent interactive session: click/type/navigate/scrape

Vision inference (N4 take_screenshot, Approach B vision_click) lives in vision_tools.py.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request

from Skynet.tools.vision_tools import _vision_model, _vision_call, vision_click

logger = logging.getLogger(__name__)


# ── Playwright browser (N1 + N5) ──────────────────────────────────────────────

# Persistent browser — created on first use, reused across all calls.
_browser = None
_playwright_ctx = None

# Persistent interactive page for N5 — separate from web_browse's temp pages.
_page = None


def _warmup_vision() -> None:
    """Pre-load the vision model into VRAM in a background thread.

    Called when a browser page is first opened so Approach B has no cold-start penalty.
    VRAM note: qwen2.5:14b + qwen2.5vl:7b together ≈ 15-16GB on RTX 5080 — Ollama
    will offload layers to RAM if needed, which slightly reduces LLM1 throughput.
    """
    def _do() -> None:
        model = _vision_model()
        try:
            payload = json.dumps({"model": model, "keep_alive": 3600}).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120):
                pass
            logger.info("Vision model warmed up: %s (VRAM loaded)", model)
        except Exception as exc:
            logger.debug("Vision warmup skipped (Ollama not ready?): %s", exc)

    threading.Thread(target=_do, daemon=True, name="vision-warmup").start()


def _unload_vision() -> None:
    """Release vision model VRAM when the browser session ends."""
    model = _vision_model()
    try:
        payload = json.dumps({"model": model, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        logger.info("Vision model unloaded from VRAM: %s", model)
    except Exception as exc:
        logger.debug("Vision unload failed (non-critical): %s", exc)


def _get_browser():
    global _browser, _playwright_ctx
    if _browser is None or not _browser.is_connected():
        from playwright.sync_api import sync_playwright
        _playwright_ctx = sync_playwright().start()
        _browser = _playwright_ctx.chromium.launch(headless=True)
        logger.info("Playwright Chromium launched")
    return _browser


def _get_page():
    """Get or create the persistent interactive page (N5)."""
    global _page
    browser = _get_browser()
    if _page is None or _page.is_closed():
        _page = browser.new_page()
        _page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        logger.info("browser_action: persistent page created")
        _warmup_vision()  # pre-load vision into VRAM — Approach B ready when needed
    return _page


def shutdown_browser() -> None:
    """Call on Nexux shutdown to cleanly close the browser and free vision VRAM."""
    global _browser, _playwright_ctx, _page
    if _page:
        try:
            _page.close()
        except Exception:
            pass
        _page = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright_ctx:
        try:
            _playwright_ctx.stop()
        except Exception:
            pass
        _playwright_ctx = None
    _unload_vision()


# ── N5 helpers ────────────────────────────────────────────────────────────────

def _format_a11y_node(node: dict, depth: int = 0, budget: list | None = None) -> list[str]:
    """Recursively format a Playwright accessibility tree node."""
    if budget is None:
        budget = [200]
    if budget[0] <= 0:
        return []

    indent = "  " * depth
    role = node.get("role", "")
    name = node.get("name", "")
    value = node.get("value", "")
    description = node.get("description", "")

    parts = [role]
    if name:
        parts.append(f'"{name}"')
    if value and str(value) != name:
        parts.append(f"value={str(value)!r}")
    if description and description != name:
        parts.append(f"desc={description!r}")

    lines = [f"{indent}{' '.join(parts)}"]
    budget[0] -= 1

    for child in node.get("children", [])[:25]:
        lines.extend(_format_a11y_node(child, depth + 1, budget))

    return lines


def _accessibility_snapshot(page) -> str:
    """Dump the page accessibility tree — call this first to understand page structure."""
    try:
        snapshot = page.accessibility.snapshot(interesting_only=True)
    except Exception as exc:
        return f"Accessibility snapshot failed: {exc}"

    if not snapshot:
        return "Page has no accessible content (empty a11y tree)."

    lines = [f"[Page: {page.title()}]", f"[URL: {page.url}]", ""]
    lines.extend(_format_a11y_node(snapshot))

    result = "\n".join(lines)
    if len(result) > 6000:
        result = result[:6000] + "\n... (tree truncated — use selector/text to target elements)"
    return result


def _find_element_approach_a(page, selector: str, text: str, role: str, timeout_ms: int):
    """
    Approach A: CSS selector → exact text → partial text → ARIA role.
    Returns (locator, method_name) or (None, None).
    Each probe uses a short timeout to fail fast before trying the next strategy.
    """
    probe_ms = min(3000, timeout_ms)

    if selector:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=probe_ms)
            return loc, "css"
        except Exception:
            pass

    if text:
        try:
            loc = page.get_by_text(text, exact=True).first
            loc.wait_for(state="visible", timeout=probe_ms)
            return loc, "exact-text"
        except Exception:
            pass
        try:
            loc = page.get_by_text(text, exact=False).first
            loc.wait_for(state="visible", timeout=probe_ms)
            return loc, "partial-text"
        except Exception:
            pass

    if role:
        try:
            kwargs = {"name": text} if text else {}
            loc = page.get_by_role(role, **kwargs).first
            loc.wait_for(state="visible", timeout=probe_ms)
            return loc, "role"
        except Exception:
            pass

    return None, None


# ── N5: browser_action ────────────────────────────────────────────────────────

def browser_action(
    action: str,
    url: str = "",
    selector: str = "",
    text: str = "",
    role: str = "",
    value: str = "",
    wait_for: str = "",
    timeout_ms: int = 15_000,
) -> str:
    """
    Interact with a persistent live browser page (N5).

    Recommended workflow:
      1. navigate(url)  — load the page
      2. get_snapshot   — read the accessibility tree to see all elements
      3. click/type/select using selector, text, or role from the snapshot

    click uses Approach A (CSS/text/role) then falls back to Approach B (vision_click) automatically.
    """
    action = (action or "").strip().lower()
    if not action:
        return (
            "action is required. Valid: navigate, get_snapshot, click, type, "
            "hover, scroll, wait, get_text, select, screenshot"
        )

    if action == "navigate":
        if not url:
            return "url is required for navigate."
        if not url.startswith(("http://", "https://")):
            return f"Invalid URL (must start with http:// or https://): {url}"
        try:
            page = _get_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = page.title()
            logger.info("browser_action navigate: %s  title=%r", url, title)
            return f"Navigated to: {url}\nTitle: {title}"
        except Exception as exc:
            return f"Navigate failed: {exc}"

    try:
        page = _get_page()
    except Exception as exc:
        return f"Browser init failed: {exc}"

    if wait_for:
        try:
            page.wait_for_selector(wait_for, timeout=min(5000, timeout_ms))
        except Exception:
            pass

    match action:
        case "get_snapshot":
            return _accessibility_snapshot(page)

        case "get_text":
            loc, method = _find_element_approach_a(page, selector, text, role, timeout_ms)
            if loc is None:
                return f"Element not found (selector={selector!r}, text={text!r}, role={role!r})"
            try:
                return f"Text [{method}]: {loc.inner_text(timeout=timeout_ms)}"
            except Exception as exc:
                return f"get_text failed: {exc}"

        case "click":
            target = selector or text or role or "(unspecified)"
            loc, method = _find_element_approach_a(page, selector, text, role, timeout_ms)
            if loc is not None:
                try:
                    loc.click(timeout=timeout_ms)
                    logger.info("browser_action click [A/%s]: %s", method, target[:80])
                    return f"Clicked [{method}]: {target}"
                except Exception as exc:
                    logger.warning("Approach A click failed (%s) — falling back to Approach B", exc)
            return vision_click(page, selector or text or role or "the primary clickable element")

        case "type":
            if not value:
                return "value is required for type."
            loc, method = _find_element_approach_a(page, selector, text, role, timeout_ms)
            if loc is None:
                return f"Input element not found (selector={selector!r}, text={text!r})"
            try:
                loc.clear(timeout=timeout_ms)
                loc.fill(value, timeout=timeout_ms)
                logger.info("browser_action type [%s]: %d chars", method, len(value))
                return f"Typed into [{method}]: {value[:80]}{'...' if len(value) > 80 else ''}"
            except Exception as exc:
                return f"Type failed: {exc}"

        case "hover":
            loc, method = _find_element_approach_a(page, selector, text, role, timeout_ms)
            if loc is None:
                return f"Element not found for hover (selector={selector!r}, text={text!r})"
            try:
                loc.hover(timeout=timeout_ms)
                return f"Hovered [{method}]: {selector or text or role}"
            except Exception as exc:
                return f"Hover failed: {exc}"

        case "scroll":
            if selector or text or role:
                loc, _ = _find_element_approach_a(page, selector, text, role, timeout_ms)
                if loc:
                    try:
                        loc.scroll_into_view_if_needed(timeout=timeout_ms)
                        return f"Scrolled to element: {selector or text or role}"
                    except Exception as exc:
                        return f"Scroll to element failed: {exc}"

            direction = (value or "down").lower()
            scroll_js = {
                "top":    "window.scrollTo(0, 0)",
                "bottom": "window.scrollTo(0, document.body.scrollHeight)",
                "up":     "window.scrollBy(0, -400)",
                "down":   "window.scrollBy(0, 400)",
            }.get(direction)
            if scroll_js is None:
                try:
                    px = int(direction)
                    scroll_js = f"window.scrollBy(0, {px})"
                except ValueError:
                    scroll_js = "window.scrollBy(0, 400)"
            try:
                page.evaluate(scroll_js)
                return f"Scrolled: {direction}"
            except Exception as exc:
                return f"Scroll failed: {exc}"

        case "wait":
            if not selector and not text:
                return "selector or text required for wait."
            try:
                if selector:
                    page.wait_for_selector(selector, timeout=timeout_ms)
                    return f"Element appeared: {selector}"
                else:
                    page.wait_for_selector(f"text={text}", timeout=timeout_ms)
                    return f"Text appeared: {text}"
            except Exception as exc:
                return f"Wait timed out: {exc}"

        case "select":
            if not value:
                return "value is required for select."
            loc, method = _find_element_approach_a(page, selector, text, role or "combobox", timeout_ms)
            if loc is None:
                return f"Select element not found (selector={selector!r}, text={text!r})"
            try:
                loc.select_option(value, timeout=timeout_ms)
                return f"Selected '{value}' in [{method}]"
            except Exception as exc:
                return f"Select failed: {exc}"

        case "screenshot":
            try:
                import base64
                img_bytes = page.screenshot(type="png")
                img_b64 = base64.b64encode(img_bytes).decode()
                prompt_text = value or "Describe the current state of this web page in detail."
                result = _vision_call(prompt_text, img_b64)
                logger.info("browser_action screenshot: %d chars", len(result))
                return f"[Browser page analyzed by {_vision_model()}]\n\n{result}"
            except Exception as exc:
                return f"Screenshot/analysis failed: {exc}"

        case _:
            return (
                f"Unknown action: {action!r}. "
                "Valid: navigate, get_snapshot, click, type, hover, scroll, wait, get_text, select, screenshot"
            )


# ── N1: web_browse ─────────────────────────────────────────────────────────────

def web_browse(url: str, selector: str = "", wait_for: str = "") -> str:
    """
    Fetch a URL using a real headless browser with JavaScript execution (N1).
    Use instead of web_fetch for JS-rendered pages, SPAs, lyrics sites, etc.
    Use browser_action when you need to interact with the page across multiple steps.
    """
    if not url:
        return "url is required."
    if not url.startswith(("http://", "https://")):
        return f"Invalid URL (must start with http:// or https://): {url}"

    try:
        browser = _get_browser()
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            page.close()
            return f"Navigation failed: {exc}"

        if wait_for:
            try:
                page.wait_for_selector(f"text={wait_for}", timeout=8_000)
            except Exception:
                pass

        try:
            if selector:
                page.wait_for_selector(selector, timeout=5_000)
                content = page.inner_text(selector).strip()
            else:
                for main_sel in ("main", "article", "#content", ".content", "body"):
                    try:
                        content = page.inner_text(main_sel).strip()
                        if len(content) > 200:
                            break
                    except Exception:
                        continue
        except Exception as exc:
            page.close()
            return f"Content extraction failed: {exc}"

        page.close()

    except Exception as exc:
        logger.warning("web_browse error for %s: %s", url, exc)
        return f"Browser error: {exc}"

    if not content:
        return f"[URL: {url}]\n\n(Page loaded but no text content found)"

    if len(content) > 8000:
        content = content[:8000] + f"\n... (truncated — {len(content)} total chars)"

    note = f"  selector={selector}" if selector else ""
    return f"[URL: {url}{note}]\n\n{content}"
