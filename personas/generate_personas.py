"""Generate US English messaging personas via Claude API.

Reads distribution targets from prompts/attributes_pool.json, samples demographic
attributes per-persona, then asks Claude to produce a full narrative persona record.
Writes one JSON object per line to the output JSONL.

Usage:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...
    python generate_personas.py --count 100 --out data/personas.jsonl
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
POOL_PATH = ROOT / "prompts" / "attributes_pool.json"
PROMPT_PATH = ROOT / "prompts" / "persona_narrative.txt"

MODEL = "claude-sonnet-4-6"


def weighted_pick(weights: dict[str, float]) -> str:
    items = list(weights.items())
    keys = [k for k, _ in items]
    probs = [p for _, p in items]
    return random.choices(keys, weights=probs, k=1)[0]


def age_from_group(group: str) -> int:
    if group == "75+":
        return random.randint(75, 92)
    lo, hi = group.split("-")
    return random.randint(int(lo), int(hi))


def sample_attributes(pool: dict) -> dict:
    sex = weighted_pick(pool["sex"])
    age_group = weighted_pick(pool["age_group"])
    age = age_from_group(age_group)
    region = weighted_pick(pool["region"])
    state = random.choice(pool["regions_to_states"][region])
    ethnicity = weighted_pick(pool["ethnicity"])
    education = weighted_pick(pool["education_level"])
    if age < 22 and education in ("Bachelor's", "Graduate"):
        education = "Some college"
    if age < 26 and education == "Graduate":
        education = "Bachelor's"
    marital = weighted_pick(pool["marital_status_by_age"][age_group])
    income = weighted_pick(pool["income_bracket_by_education"][education])
    msg_anchors = pool["messaging_traits_by_age"][age_group]
    return {
        "sex": sex,
        "age": age,
        "age_group": age_group,
        "region": region,
        "state": state,
        "ethnicity": ethnicity,
        "education_level": education,
        "marital_status": marital,
        "income_bracket": income,
        "messaging_anchors": msg_anchors,
    }


def call_claude(client: Anthropic, prompt_template: str, attrs: dict) -> dict:
    prompt = prompt_template.replace(
        "{attributes}", json.dumps(attrs, indent=2, ensure_ascii=False)
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system="You are a synthetic data generator. Output exactly one JSON object, no commentary.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return json.loads(text)


def merge(attrs: dict, narrative: dict) -> dict:
    out = {"uuid": str(uuid.uuid4())}
    out["first_name"] = narrative["first_name"]
    out["last_name"] = narrative["last_name"]
    out["sex"] = attrs["sex"]
    out["age"] = attrs["age"]
    out["region"] = attrs["region"]
    out["state"] = attrs["state"]
    out["city"] = narrative["city"]
    out["ethnicity"] = attrs["ethnicity"]
    out["native_language"] = narrative["native_language"]
    out["education_level"] = attrs["education_level"]
    out["marital_status"] = attrs["marital_status"]
    out["household_size"] = narrative["household_size"]
    out["occupation"] = narrative["occupation"]
    out["income_bracket"] = attrs["income_bracket"]
    for k in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        out[k] = narrative[k]
    for k in ("communication_style", "emoji_density", "abbreviation_use",
              "avg_message_length", "punctuation_style", "capitalization_style",
              "preferred_platforms", "slang_register",
              "professional_persona", "social_persona", "messaging_persona",
              "hobbies_and_interests", "core_values"):
        out[k] = narrative[k]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--out", type=str, default="data/personas.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    pool = json.loads(POOL_PATH.read_text())
    prompt_template = PROMPT_PATH.read_text()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = Anthropic(api_key=api_key)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for _ in tqdm(range(args.count), desc="personas"):
            attrs = sample_attributes(pool)
            try:
                narrative = call_claude(client, prompt_template, attrs)
                record = merge(attrs, narrative)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as e:
                print(f"  skip: {e}", file=sys.stderr)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
