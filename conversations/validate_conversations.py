"""Validate generated conversations.jsonl.

Checks:
  - structural correctness (required fields, enum values, message sub-objects)
  - persona-level references (uuids exist in personas.jsonl, perspective is a participant)
  - platform appears in both personas' preferred_platforms
  - message timing is non-decreasing
  - both participants speak
  - label consistency:
      trigger=yes -> action in 9-enum, negative_reason=None
      trigger=no  -> action=None, negative_reason in 5-enum
  - reports distributions over trigger, action, negative_reason, platform,
    relationship, boundary_case, message-count histogram

Usage:
    python validate_conversations.py
    python validate_conversations.py --in data/conversations.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
PERSONAS_PATH = ROOT.parent / "personas" / "data" / "personas.jsonl"

ACTIONS = {
    "check_weather", "open_maps", "order_food", "send_gift", "send_money",
    "set_reminder", "share_photo", "take_note", "web_search",
}
NEGATIVE_REASONS = {
    "pure_chitchat", "action_completed_in_convo", "other_party_action",
    "already_resolved_elsewhere", "ambiguous_boundary",
}
RELATIONSHIPS = {
    "friends", "close_friends", "family_immediate", "family_extended",
    "romantic_partner", "dating_early", "coworkers", "manager_report",
    "classmates", "neighbors", "acquaintance", "online_friend", "service_customer",
}
PLATFORMS = {
    "SMS", "iMessage", "WhatsApp", "Slack", "Discord", "Instagram_DM",
    "Snapchat", "Facebook_Messenger", "email", "Teams", "Telegram",
}

REQUIRED_FIELDS = [
    "conversation_id", "persona_a_uuid", "persona_b_uuid",
    "perspective_persona_uuid", "relationship", "platform",
    "topic_text", "messages", "trigger", "action",
    "negative_reason", "boundary_case", "rationale",
]


def load_personas() -> dict[str, dict]:
    return {
        json.loads(l)["uuid"]: json.loads(l)
        for l in PERSONAS_PATH.read_text().splitlines() if l.strip()
    }


def validate_record(rec: dict, personas: dict[str, dict], line_no: int) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in rec:
            errs.append(f"line {line_no}: missing field '{f}'")
    if errs:
        return errs

    a_uuid = rec["persona_a_uuid"]
    b_uuid = rec["persona_b_uuid"]
    if a_uuid == b_uuid:
        errs.append(f"line {line_no}: persona_a_uuid == persona_b_uuid")
    if a_uuid not in personas:
        errs.append(f"line {line_no}: persona_a_uuid not in personas.jsonl")
    if b_uuid not in personas:
        errs.append(f"line {line_no}: persona_b_uuid not in personas.jsonl")
    if rec["perspective_persona_uuid"] not in {a_uuid, b_uuid}:
        errs.append(f"line {line_no}: perspective_persona_uuid not a participant")

    if rec["relationship"] not in RELATIONSHIPS:
        errs.append(f"line {line_no}: bad relationship={rec['relationship']!r}")
    if rec["platform"] not in PLATFORMS:
        errs.append(f"line {line_no}: bad platform={rec['platform']!r}")

    if a_uuid in personas and b_uuid in personas:
        a_plat = set(personas[a_uuid].get("preferred_platforms", []))
        b_plat = set(personas[b_uuid].get("preferred_platforms", []))
        if rec["platform"] not in a_plat or rec["platform"] not in b_plat:
            errs.append(f"line {line_no}: platform {rec['platform']!r} not in both personas' preferred_platforms")

    msgs = rec.get("messages")
    if not isinstance(msgs, list):
        errs.append(f"line {line_no}: messages not a list")
        return errs
    if not (4 <= len(msgs) <= 20):
        errs.append(f"line {line_no}: message count {len(msgs)} outside [4, 20]")
    senders = set()
    last_t = -1
    for i, m in enumerate(msgs):
        if not isinstance(m, dict):
            errs.append(f"line {line_no} msg {i}: not an object")
            continue
        if m.get("sender_uuid") not in {a_uuid, b_uuid}:
            errs.append(f"line {line_no} msg {i}: sender_uuid not a participant")
        if not isinstance(m.get("text"), str) or not m["text"].strip():
            errs.append(f"line {line_no} msg {i}: empty text")
        t = m.get("t_offset_min")
        if not isinstance(t, int):
            errs.append(f"line {line_no} msg {i}: t_offset_min not an int")
        elif t < last_t:
            errs.append(f"line {line_no} msg {i}: t_offset_min {t} < previous {last_t}")
        else:
            last_t = t
        if m.get("sender_uuid") in {a_uuid, b_uuid}:
            senders.add(m["sender_uuid"])
    if len(senders) < 2 and msgs:
        errs.append(f"line {line_no}: only one persona spoke")

    trig = rec.get("trigger")
    act = rec.get("action")
    neg = rec.get("negative_reason")
    if trig == "yes":
        if act not in ACTIONS:
            errs.append(f"line {line_no}: trigger=yes but action={act!r} not in 9-enum")
        if neg is not None:
            errs.append(f"line {line_no}: trigger=yes but negative_reason={neg!r} (should be null)")
    elif trig == "no":
        if act is not None:
            errs.append(f"line {line_no}: trigger=no but action={act!r} (should be null)")
        if neg not in NEGATIVE_REASONS:
            errs.append(f"line {line_no}: trigger=no but negative_reason={neg!r} not in 5-enum")
    else:
        errs.append(f"line {line_no}: bad trigger={trig!r}")

    if not isinstance(rec.get("boundary_case"), bool):
        errs.append(f"line {line_no}: boundary_case must be bool")
    if not isinstance(rec.get("rationale"), str) or not rec["rationale"].strip():
        errs.append(f"line {line_no}: missing/empty rationale")

    return errs


def report_distributions(records: list[dict]) -> None:
    n = len(records)
    print(f"\n=== Distributions across {n} conversations ===\n")

    trig = Counter(r["trigger"] for r in records)
    print("trigger:")
    for k, v in trig.most_common():
        print(f"  {k:30s} {v:5d}  ({100*v/n:.0f}%)")

    actions = Counter(r["action"] for r in records if r["trigger"] == "yes")
    print("\naction (within trigger=yes):")
    for k, v in actions.most_common():
        print(f"  {k:30s} {v:5d}")

    neg = Counter(r["negative_reason"] for r in records if r["trigger"] == "no")
    print("\nnegative_reason (within trigger=no):")
    for k, v in neg.most_common():
        print(f"  {k:30s} {v:5d}")

    plat = Counter(r["platform"] for r in records)
    print("\nplatform:")
    for k, v in plat.most_common():
        print(f"  {k:30s} {v:5d}")

    rel = Counter(r["relationship"] for r in records)
    print("\nrelationship:")
    for k, v in rel.most_common():
        print(f"  {k:30s} {v:5d}")

    bc = sum(1 for r in records if r.get("boundary_case"))
    print(f"\nboundary_case=true: {bc} ({100*bc/n:.1f}%)")

    msg_counts = [len(r["messages"]) for r in records]
    if msg_counts:
        print(f"\nmessage counts: min={min(msg_counts)}, max={max(msg_counts)}, "
              f"mean={sum(msg_counts)/len(msg_counts):.1f}")
        bands = Counter()
        for c in msg_counts:
            if c <= 6: bands["4-6"] += 1
            elif c <= 10: bands["7-10"] += 1
            elif c <= 14: bands["11-14"] += 1
            else: bands["15-20"] += 1
        for k in ("4-6", "7-10", "11-14", "15-20"):
            print(f"  msgs {k:6s} {bands.get(k, 0):5d}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/conversations.jsonl")
    ap.add_argument("--examples", action="store_true",
                    help="Validate examples/sample_conversations.jsonl instead")
    args = ap.parse_args()

    path = ROOT / ("examples/sample_conversations.jsonl" if args.examples else args.inp)
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 1

    personas = load_personas()

    records: list[dict] = []
    errors: list[str] = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: bad JSON: {e}")
            continue
        errors.extend(validate_record(rec, personas, i))
        records.append(rec)

    print(f"=== Conversations: {len(records)} entries from {path} ===")
    if errors:
        print(f"\n!! {len(errors)} errors:")
        for e in errors[:80]:
            print("  -", e)
        if len(errors) > 80:
            print(f"  ... and {len(errors)-80} more")
    else:
        print("OK no structural errors.")

    if records:
        report_distributions(records)

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
