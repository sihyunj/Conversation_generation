"""Validate generated personas.jsonl and topics.jsonl.

Checks structural correctness (required fields, enum values), uniqueness, and
reports the demographic distribution so you can eyeball coverage. Also flags
plausibility violations defined in schema.md.

Usage:
    python validate.py
    python validate.py --personas data/personas.jsonl --topics data/topics.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent

REQUIRED_PERSONA_FIELDS = [
    "uuid", "first_name", "last_name", "sex", "age",
    "region", "state", "city",
    "ethnicity", "native_language", "education_level", "marital_status",
    "household_size", "occupation", "income_bracket",
    "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism",
    "communication_style", "emoji_density", "abbreviation_use",
    "avg_message_length", "punctuation_style", "capitalization_style",
    "preferred_platforms", "slang_register",
    "professional_persona", "social_persona", "messaging_persona",
    "hobbies_and_interests", "core_values",
]

ENUMS = {
    "sex": {"Male", "Female"},
    "region": {"Northeast", "Midwest", "South", "West"},
    "ethnicity": {"White", "Hispanic", "Black", "Asian", "Multiracial", "Native American"},
    "education_level": {"Less than HS", "HS diploma", "Some college", "Associate", "Bachelor's", "Graduate"},
    "marital_status": {"Single", "Married", "Divorced", "Widowed", "Cohabiting"},
    "income_bracket": {"under_25k", "25-50k", "50-75k", "75-100k", "100-150k", "150k+"},
    "communication_style": {"formal", "professional", "casual", "playful", "terse"},
    "emoji_density": {"none", "low", "medium", "high"},
    "abbreviation_use": {"none", "minimal", "moderate", "heavy"},
    "avg_message_length": {"very_short", "short", "medium", "long"},
    "punctuation_style": {"minimal", "standard", "expressive"},
    "capitalization_style": {"lowercase", "sentence_case", "proper", "random"},
    "slang_register": {"none", "mild", "moderate", "heavy_genz", "heavy_millennial", "regional"},
}

PLATFORM_VALUES = {
    "SMS", "iMessage", "WhatsApp", "Slack", "Discord", "Instagram_DM",
    "Snapchat", "Facebook_Messenger", "email", "Teams", "Telegram",
}

REQUIRED_TOPIC_FIELDS = ["topic_id", "persona_a_uuid", "persona_b_uuid",
                        "relationship", "platform", "topic", "tone", "opener_hint"]

TONE_VALUES = {"casual", "serious", "playful", "tense", "supportive",
              "transactional", "flirty", "excited", "professional", "formal"}

RELATIONSHIP_VALUES = {
    "friends", "close_friends", "family_immediate", "family_extended",
    "romantic_partner", "dating_early", "coworkers", "manager_report",
    "classmates", "neighbors", "acquaintance", "online_friend", "service_customer",
}


def validate_personas(path: Path) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    personas: list[dict] = []
    seen_uuids: set[str] = set()

    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            p = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: invalid JSON: {e}")
            continue

        for f in REQUIRED_PERSONA_FIELDS:
            if f not in p:
                errors.append(f"line {i} ({p.get('first_name','?')}): missing field '{f}'")

        for f, allowed in ENUMS.items():
            if f in p and p[f] not in allowed:
                errors.append(f"line {i}: bad {f}={p[f]!r}")

        if "preferred_platforms" in p:
            if not isinstance(p["preferred_platforms"], list):
                errors.append(f"line {i}: preferred_platforms not a list")
            else:
                bad = [pl for pl in p["preferred_platforms"] if pl not in PLATFORM_VALUES]
                if bad:
                    errors.append(f"line {i}: bad platforms {bad}")

        for k in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
            if k in p and not (0 <= p[k] <= 100):
                errors.append(f"line {i}: {k}={p[k]} out of [0,100]")

        if "age" in p and not (18 <= p["age"] <= 100):
            errors.append(f"line {i}: age={p['age']} out of range")

        if "uuid" in p:
            if p["uuid"] in seen_uuids:
                errors.append(f"line {i}: duplicate uuid {p['uuid']}")
            seen_uuids.add(p["uuid"])

        if p.get("slang_register") == "heavy_genz" and p.get("age", 0) > 30:
            errors.append(f"line {i}: heavy_genz with age={p['age']}")
        if p.get("slang_register") == "heavy_millennial":
            if not (26 <= p.get("age", 0) <= 46):
                errors.append(f"line {i}: heavy_millennial with age={p['age']}")
        if p.get("age", 0) > 55:
            forbidden = {"Discord", "Snapchat"} & set(p.get("preferred_platforms", []))
            if forbidden:
                errors.append(f"line {i}: platforms {forbidden} unlikely at age {p['age']}")

        personas.append(p)

    return personas, errors


def report_distributions(personas: list[dict]) -> None:
    n = len(personas)
    print(f"\n=== Distributions across {n} personas ===")
    for field in ("sex", "region", "ethnicity", "education_level",
                  "marital_status", "income_bracket",
                  "communication_style", "emoji_density", "slang_register"):
        c = Counter(p.get(field) for p in personas)
        print(f"\n{field}:")
        for k, v in c.most_common():
            print(f"  {k!r:30s} {v:3d}  ({100*v/n:.0f}%)")

    ages = [p["age"] for p in personas if "age" in p]
    bands = Counter()
    for a in ages:
        if a < 25: bands["18-24"] += 1
        elif a < 35: bands["25-34"] += 1
        elif a < 45: bands["35-44"] += 1
        elif a < 55: bands["45-54"] += 1
        elif a < 65: bands["55-64"] += 1
        elif a < 75: bands["65-74"] += 1
        else: bands["75+"] += 1
    print(f"\nage_band:")
    for k in ("18-24","25-34","35-44","45-54","55-64","65-74","75+"):
        v = bands.get(k, 0)
        print(f"  {k:30s} {v:3d}  ({100*v/n:.0f}%)")

    plats = Counter()
    for p in personas:
        for pl in p.get("preferred_platforms", []):
            plats[pl] += 1
    print(f"\npreferred_platforms (mentions):")
    for k, v in plats.most_common():
        print(f"  {k:30s} {v:3d}")

    occs = Counter(p.get("occupation") for p in personas)
    print(f"\noccupations: {len(occs)} unique out of {n} personas")
    print(f"  duplicates: {[(k,v) for k,v in occs.items() if v > 1]}")


def validate_topics(path: Path, persona_uuids: set[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"topics file not found: {path}"]

    seen_topic_ids: set[str] = set()
    counts = Counter()
    rels = Counter()
    tones = Counter()
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"topics line {i}: bad JSON: {e}")
            continue
        for f in REQUIRED_TOPIC_FIELDS:
            if f not in t:
                errors.append(f"topics line {i}: missing field '{f}'")
        if t.get("topic_id") in seen_topic_ids:
            errors.append(f"topics line {i}: duplicate topic_id")
        seen_topic_ids.add(t.get("topic_id"))
        if t.get("persona_a_uuid") not in persona_uuids:
            errors.append(f"topics line {i}: persona_a_uuid not found")
        if t.get("persona_b_uuid") not in persona_uuids:
            errors.append(f"topics line {i}: persona_b_uuid not found")
        if t.get("persona_a_uuid") == t.get("persona_b_uuid"):
            errors.append(f"topics line {i}: same persona on both sides")
        if t.get("relationship") not in RELATIONSHIP_VALUES:
            errors.append(f"topics line {i}: bad relationship={t.get('relationship')!r}")
        if t.get("tone") not in TONE_VALUES:
            errors.append(f"topics line {i}: bad tone={t.get('tone')!r}")
        if t.get("platform") not in PLATFORM_VALUES:
            errors.append(f"topics line {i}: bad platform={t.get('platform')!r}")
        counts["total"] += 1
        rels[t.get("relationship")] += 1
        tones[t.get("tone")] += 1

    print(f"\n=== Topics: {counts['total']} entries ===")
    print("\nrelationship:")
    for k, v in rels.most_common():
        print(f"  {k:30s} {v:3d}")
    print("\ntone:")
    for k, v in tones.most_common():
        print(f"  {k:30s} {v:3d}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="data/personas.jsonl")
    ap.add_argument("--topics", default="data/topics.jsonl")
    args = ap.parse_args()

    personas_path = ROOT / args.personas
    topics_path = ROOT / args.topics

    personas, errs = validate_personas(personas_path)
    print(f"=== Personas: {len(personas)} entries from {personas_path.name} ===")
    if errs:
        print(f"\n!! {len(errs)} errors:")
        for e in errs[:50]:
            print("  -", e)
        if len(errs) > 50:
            print(f"  ... and {len(errs)-50} more")
    else:
        print("OK no structural errors.")

    if personas:
        report_distributions(personas)

    persona_uuids = {p["uuid"] for p in personas if "uuid" in p}
    topic_errs = validate_topics(topics_path, persona_uuids)
    if topic_errs:
        print(f"\n!! {len(topic_errs)} topic errors:")
        for e in topic_errs[:50]:
            print("  -", e)

    return 0 if not (errs or topic_errs) else 1


if __name__ == "__main__":
    sys.exit(main())
