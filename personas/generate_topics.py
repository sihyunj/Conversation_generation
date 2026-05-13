"""Generate persona-pair conversation topics via Claude API.

Reads personas.jsonl, samples plausible pairs (filtering implausible age gaps,
no-platform-overlap, etc.), then asks Claude for 1-3 realistic conversation
topics per pair. Writes one topic JSON per line.

Usage:
    python generate_topics.py --in data/personas.jsonl --out data/topics.jsonl --pairs 300
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import uuid
from pathlib import Path

from anthropic import Anthropic
from tqdm import tqdm

ROOT = Path(__file__).parent
PROMPT_PATH = ROOT / "prompts" / "topics_prompt.txt"
MODEL = "claude-sonnet-4-6"

RELATIONSHIPS = [
    "friends", "close_friends", "family_immediate", "family_extended",
    "romantic_partner", "dating_early", "coworkers", "manager_report",
    "classmates", "neighbors", "acquaintance", "online_friend", "service_customer",
]

ROMANTIC_REL = {"romantic_partner", "dating_early"}
PEER_REL = {"friends", "close_friends", "classmates", "neighbors", "acquaintance"}


def is_plausible_pair(a: dict, b: dict, rel: str) -> tuple[bool, str | None]:
    age_gap = abs(a["age"] - b["age"])

    if rel in ROMANTIC_REL or rel in PEER_REL:
        if age_gap > 25:
            return False, "age_gap_too_large_for_peer_or_romantic"

    if rel == "classmates":
        if age_gap > 12:
            return False, "classmates_age_gap"
        if a["age"] > 70 or b["age"] > 70:
            return False, "classmates_too_old"

    if rel == "manager_report" and age_gap > 25:
        return False, "manager_report_age_gap"

    if rel in ROMANTIC_REL or rel == "dating_early":
        # don't pair near family in a romantic way (age proxy + last name shared)
        if a["last_name"] == b["last_name"] and age_gap < 30:
            return False, "same_last_name_romantic"

    if rel == "online_friend":
        online_plats = {"Discord", "Instagram_DM", "Snapchat", "Telegram"}
        if not (set(a["preferred_platforms"]) & online_plats and set(b["preferred_platforms"]) & online_plats):
            return False, "no_online_platform"

    overlap = set(a["preferred_platforms"]) & set(b["preferred_platforms"])
    if not overlap:
        return False, "no_platform_overlap"

    if rel in ROMANTIC_REL:
        if (a["marital_status"] == "Married") != (b["marital_status"] == "Married"):
            # one married, one not — discourage but allow occasionally
            if random.random() > 0.05:
                return False, "marital_mismatch_for_romantic"
        if a["sex"] == b["sex"]:
            # allow but rarer
            if random.random() > 0.15:
                return False, "rare_same_sex_romantic_in_dataset"

    return True, None


def sample_pair(personas: list[dict], rng: random.Random) -> tuple[dict, dict, str] | None:
    for _ in range(50):
        a, b = rng.sample(personas, 2)
        rel = rng.choice(RELATIONSHIPS)
        ok, _ = is_plausible_pair(a, b, rel)
        if ok:
            return a, b, rel
    return None


def call_claude(client: Anthropic, template: str, a: dict, b: dict, rel: str) -> list[dict]:
    prompt = (template
              .replace("{persona_a}", json.dumps(a, ensure_ascii=False))
              .replace("{persona_b}", json.dumps(b, ensure_ascii=False))
              .replace("{relationship}", rel))
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system="You are a synthetic data generator. Output exactly one JSON list, no commentary.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    data = json.loads(text)
    return data if isinstance(data, list) else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/personas.jsonl")
    ap.add_argument("--out", default="data/topics.jsonl")
    ap.add_argument("--pairs", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    personas = [json.loads(l) for l in (ROOT / args.inp).read_text().splitlines() if l.strip()]
    template = PROMPT_PATH.read_text()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = Anthropic(api_key=api_key)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w") as f:
        pbar = tqdm(total=args.pairs, desc="pairs")
        while written < args.pairs:
            picked = sample_pair(personas, rng)
            if not picked:
                continue
            a, b, rel = picked
            try:
                topics = call_claude(client, template, a, b, rel)
            except Exception as e:
                print(f"  skip: {e}", file=sys.stderr)
                continue
            for t in topics:
                rec = {
                    "topic_id": str(uuid.uuid4()),
                    "persona_a_uuid": a["uuid"],
                    "persona_b_uuid": b["uuid"],
                    "relationship": rel,
                    "platform": t.get("platform"),
                    "topic": t.get("topic"),
                    "tone": t.get("tone"),
                    "opener_hint": t.get("opener_hint"),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                written += 1
                pbar.update(1)
                if written >= args.pairs:
                    break
        pbar.close()

    print(f"Wrote {written} topics to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
