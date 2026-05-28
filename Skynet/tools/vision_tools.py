"""Vision model inference tools.

N4: take_screenshot — capture desktop screen and analyze with qwen2.5vl
    vision_click     — locate element by screenshot + vision, return click result (used by browser_action Approach B)
    _vision_call     — shared HTTP helper for all vision inference
"""
from __future__ import annotations

import base64
import json
import logging
import re
import urllib.request

logger = logging.getLogger(__name__)


def _vision_model() -> str:
    try:
        import yaml
        with open("config/settings.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("vision", {}).get("model", "qwen2.5vl:7b")
    except Exception:
        return "qwen2.5vl:7b"


def _vision_call(prompt: str, img_b64: str, timeout: int = 120) -> str:
    """Send an image + prompt to the configured vision model. Returns the text response."""
    model = _vision_model()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
        "stream": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response = json.loads(resp.read())
    return response.get("message", {}).get("content", "(no output from vision model)")


def take_screenshot(prompt: str = "Describe everything you see on screen in detail.") -> str:
    """Capture the primary monitor and analyze it with the vision model (N4)."""
    try:
        import mss
        import mss.tools
    except ImportError:
        return "Screenshot requires mss: pip install mss"

    try:
        with mss.MSS() as sct:
            monitor = sct.monitors[1]  # [1] = primary; [0] = all combined
            capture = sct.grab(monitor)
            img_bytes = mss.tools.to_png(capture.rgb, capture.size)
            width, height = capture.size
    except Exception as exc:
        return f"Screen capture failed: {exc}"

    logger.info("Screenshot captured: %dx%d px (%d KB)", width, height, len(img_bytes) // 1024)

    img_b64 = base64.b64encode(img_bytes).decode()
    try:
        result = _vision_call(prompt, img_b64)
    except Exception as exc:
        return f"Vision model error: {exc}"

    logger.info("Screenshot analysis: %d chars via %s", len(result), _vision_model())
    return f"[Screenshot {width}x{height} analyzed by {_vision_model()}]\n\n{result}"


def vision_click(page, target_description: str) -> str:
    """
    Approach B: browser page screenshot → qwen2.5vl → pixel coordinates → mouse.click.
    Called by browser_action when Approach A (accessibility tree) cannot find the element.
    """
    try:
        img_bytes = page.screenshot(type="png")
    except Exception as exc:
        return f"Approach B: page screenshot failed: {exc}"

    img_b64 = base64.b64encode(img_bytes).decode()

    try:
        dims = page.evaluate("() => [window.innerWidth, window.innerHeight]")
        width, height = int(dims[0]), int(dims[1])
    except Exception:
        width, height = 1280, 720

    prompt = (
        f'Locate the element matching: "{target_description}"\n'
        f"Image dimensions: {width}x{height} pixels.\n"
        "Return JSON only (no markdown, no explanation):\n"
        '{"found": true, "x": <pixel_x>, "y": <pixel_y>}\n'
        'or {"found": false} if the element is not visible.'
    )

    try:
        raw = _vision_call(prompt, img_b64)
    except Exception as exc:
        return f"Approach B: vision model error: {exc}"

    clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        result = json.loads(clean)
    except Exception:
        m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if not m:
            return f"Approach B: unparseable vision response: {raw[:200]}"
        try:
            result = json.loads(m.group())
        except Exception:
            return f"Approach B: could not parse vision response: {raw[:200]}"

    if not result.get("found"):
        return f"Approach B: vision model could not locate: {target_description}"

    x, y = result.get("x"), result.get("y")
    if x is None or y is None:
        return f"Approach B: found=true but no coordinates: {result}"

    try:
        page.mouse.click(float(x), float(y))
        logger.info("Approach B click at (%s, %s) for: %s", x, y, target_description[:80])
        return f"Clicked at ({x}, {y}) via vision [Approach B]"
    except Exception as exc:
        return f"Approach B: mouse click failed at ({x}, {y}): {exc}"
