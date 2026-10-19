#!/usr/bin/env python3
"""Generate the game's illustration set in parallel, resumable."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_image import request_image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "image_manifest.json"
LOCK = threading.Lock()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated ids")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        items = [it for it in items if it["id"] in wanted]

    jobs = []
    for it in items:
        out = ROOT / it["out"]
        if out.exists() and not args.force:
            print(f"skip {it['id']} (exists)")
            continue
        jobs.append((it, out))

    def run(it, out):
        prompt = it["prompt"]
        if not prompt.startswith("Hand-painted storybook"):
            prompt = (
                "Hand-painted storybook illustration for a cozy low-poly diorama exploration game. "
                "Soft gouache and fine paper grain, faceted low-poly silhouettes, cinematic atmospheric "
                "lighting, gentle volumetric haze, luminous lantern accents, harmonious muted palette, "
                "delicate detail, no text, no letters, no watermark, no logo, no user interface.\n\n"
                + prompt
            )
        t0 = time.time()
        data = request_image(prompt, it.get("size", "1536x1024"))
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(out)
        return it["id"], out, len(data), time.time() - t0

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run, it, out): it for it, out in jobs}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                iid, out, size, dt = fut.result()
                print(f"OK {iid} {size//1024}KB {dt:.1f}s -> {out}", flush=True)
            except Exception as exc:
                failures.append((it["id"], str(exc)))
                print(f"FAIL {it['id']}: {exc}", flush=True)
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
