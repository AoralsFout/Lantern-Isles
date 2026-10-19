#!/usr/bin/env python3
"""Generate images through the OpenAI-compatible image endpoint.

The API key is read from the IMGKEY environment variable and is never written
to disk. Only the image generation endpoint is used.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("IMG_BASE", "http://101.133.232.176:11451/v1")
MODEL = os.environ.get("IMG_MODEL", "gpt-image-2.5")

STYLE = (
    "Hand-painted storybook illustration for a cozy low-poly diorama exploration game. "
    "Soft gouache and fine paper grain, faceted low-poly silhouettes, cinematic atmospheric "
    "lighting, gentle volumetric haze, luminous lantern accents, harmonious muted palette, "
    "delicate detail, no text, no letters, no watermark, no logo, no user interface."
)


def request_image(prompt: str, size: str = "1536x1024", retries: int = 3) -> bytes:
    key = os.environ.get("IMGKEY")
    if not key:
        raise RuntimeError("IMGKEY is not set")
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "size": size,
        "quality": "high",
        "n": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/images/generations",
        data=payload,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            item = body["data"][0]
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"])
            if item.get("url"):
                with urllib.request.urlopen(item["url"], timeout=120) as ir:
                    return ir.read()
            raise RuntimeError("No image payload in response")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            detail = ""
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8", "replace")[:500]
                except Exception:
                    pass
            print(f"  attempt {attempt + 1} failed: {exc} {detail}", flush=True)
            time.sleep(4 + attempt * 5)
    raise RuntimeError(f"Image generation failed: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1536x1024")
    args = ap.parse_args()

    prompt = args.prompt.strip()
    if not prompt.startswith("Hand-painted storybook"):
        prompt = STYLE + "\n\n" + prompt
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"generating -> {out}", flush=True)
    data = request_image(prompt, args.size)
    out.write_bytes(data)
    print(f"saved {out} ({len(data)} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
