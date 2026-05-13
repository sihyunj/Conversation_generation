"""Generate labeled multi-turn messaging conversations via Claude API.

Pipeline (per conversation):
    1. Pre-sampled balanced label (trigger + action OR negative_reason).
    2. Random persona pair from personas/data/personas.jsonl with platform overlap
       and target-action plausibility.
    3. Random perspective ("me") from the two participants.
    4. Random platform from the pair's preferred-platform overlap.
    5. Build conditioning prompt, call Claude, parse JSON output.
    6. Validate the per-record contract before writing.

Usage:
    pip install -r ../personas/requirements.txt
    export ANTHROPIC_API_KEY=...
    python generate_conversations.py --count 1000 --out data/conversations.jsonl
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
PERSONAS_PATH = ROOT.parent / "personas" / "data" / "personas.jsonl"
PROMPT_PATH = ROOT / "prompts" / "conv_template.txt"
ACTIONS_PATH = ROOT / "prompts" / "action_triggers.json"
REASONS_PATH = ROOT / "prompts" / "negative_reasons.json"

MODEL = "claude-sonnet-4-6"

ACTIONS = [
    "check_weather", "open_maps", "order_food", "send_gift", "send_money",
    "set_reminder", "share_photo", "take_note", "web_search",
]
NEGATIVE_REASONS = [
    "pure_chitchat", "action_completed_in_convo", "other_party_action",
    "already_resolved_elsewhere", "ambiguous_boundary",
]
RELATIONSHIPS = [
    "friends", "close_friends", "family_immediate", "family_extended",
    "romantic_partner", "dating_early", "coworkers", "manager_report",
    "classmates", "neighbors", "acquaintance", "online_friend", "service_customer",
]


def make_label_schedule(n: int, yes_ratio: float, rng: random.Random) -> list[dict]:
    """Pre-sample target labels with balanced distribution.

    yes_ratio controls the trigger=yes fraction; the remainder is split across
    the 5 negative-reason categories. Both halves are sub-balanced evenly.
    """
    n_yes = round(n * yes_ratio)
    n_no = n - n_yes

    def split_evenly(total: int, k: int) -> list[int]:
        base = total // k
        extra = total - base * k
        return [base + (1 if i < extra else 0) for i in range(k)]

    yes_per = split_evenly(n_yes, len(ACTIONS))
    no_per = split_evenly(n_no, len(NEGATIVE_REASONS))

    schedule: list[dict] = []
    for action, c in zip(ACTIONS, yes_per):
        for _ in range(c):
            schedule.append({"trigger": "yes", "action": action, "negative_reason": None})
    for reason, c in zip(NEGATIVE_REASONS, no_per):
        for _ in range(c):
            schedule.append({"trigger": "no", "action": None, "negative_reason": reason})

    rng.shuffle(schedule)
    return schedule


def plausible_pair_for_action(a: dict, b: dict, action: str | None,
                              relationship: str, rng: random.Random) -> bool:
    """Soft plausibility checks for (persona_a, persona_b, action, relationship).

    Same age/relationship guards as the topic generator, plus action-specific
    quick checks (e.g., very old personas rarely use P2P payment apps).
    """
    age_gap = abs(a["age"] - b["age"])

    PEER = {"friends", "close_friends", "classmates", "neighbors", "acquaintance"}
    ROMANTIC = {"romantic_partner", "dating_early"}

    if relationship in PEER or relationship in ROMANTIC:
        if age_gap > 25:
            return False
    if relationship == "classmates":
        if age_gap > 12 or max(a["age"], b["age"]) > 70:
            return False
    if relationship == "manager_report" and age_gap > 25:
        return False
    if relationship in ROMANTIC and a["last_name"] == b["last_name"] and age_gap < 30:
        return False

    if relationship == "online_friend":
        online = {"Discord", "Instagram_DM", "Snapchat", "Telegram"}
        if not (set(a["preferred_platforms"]) & online and set(b["preferred_platforms"]) & online):
            return False

    overlap = set(a["preferred_platforms"]) & set(b["preferred_platforms"])
    if not overlap:
        return False

    # action-specific soft filters
    if action == "send_money":
        # P2P payments uncommon for personas over ~75
        if a["age"] > 78 and rng.random() > 0.05:
            return False
    if action == "share_photo":
        photo_capable = {"iMessage", "WhatsApp", "Instagram_DM", "Snapchat",
                         "Facebook_Messenger", "SMS"}
        if not overlap & photo_capable:
            return False
    if action == "send_gift":
        # service_customer is an odd context for gift suggestions
        if relationship == "service_customer":
            return False
    if action == "set_reminder":
        # Most natural in non-stranger contexts
        if relationship == "acquaintance" and rng.random() > 0.2:
            return False

    return True


def sample_pair(personas: list[dict], target_label: dict, rng: random.Random,
                max_tries: int = 80):
    for _ in range(max_tries):
        a, b = rng.sample(personas, 2)
        rel = rng.choice(RELATIONSHIPS)
        if not plausible_pair_for_action(a, b, target_label["action"], rel, rng):
            continue
        overlap = sorted(set(a["preferred_platforms"]) & set(b["preferred_platforms"]))
        platform = rng.choice(overlap)
        perspective = rng.choice([a, b])
        return a, b, perspective, platform, rel
    return None


def trim_persona(p: dict) -> dict:
    """Keep only the fields the generator actually needs in the prompt."""
    keep = [
        "uuid", "first_name", "last_name", "sex", "age", "city", "state",
        "occupation", "native_language", "communication_style", "emoji_density",
        "abbreviation_use", "avg_message_length", "punctuation_style",
        "capitalization_style", "preferred_platforms", "slang_register",
        "messaging_persona", "social_persona", "hobbies_and_interests",
    ]
    return {k: p[k] for k in keep if k in p}


def build_prompt(template: str, actions_g: dict, reasons_g: dict,
                 a: dict, b: dict, perspective: dict, platform: str,
                 relationship: str, target: dict) -> str:
    if target["trigger"] == "yes":
        guidance = actions_g[target["action"]]
    else:
        guidance = reasons_g[target["negative_reason"]]
    return (template
            .replace("{persona_a_json}", json.dumps(trim_persona(a), ensure_ascii=False, indent=2))
            .replace("{persona_b_json}", json.dumps(trim_persona(b), ensure_ascii=False, indent=2))
            .replace("{perspective_name}", f"{perspective['first_name']} {perspective['last_name']}")
            .replace("{perspective_uuid}", perspective["uuid"])
            .replace("{relationship}", relationship)
            .replace("{platform}", platform)
            .replace("{trigger}", target["trigger"])
            .replace("{action}", str(target["action"]))
            .replace("{negative_reason}", str(target["negative_reason"]))
            .replace("{label_guidance}", json.dumps(guidance, ensure_ascii=False, indent=2))
            .replace("{persona_a_uuid}", a["uuid"])
            .replace("{persona_b_uuid}", b["uuid"]))


def call_claude(client: Anthropic, prompt: str) -> dict:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system="You are a synthetic data generator. Output exactly one JSON object, no markdown, no commentary.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return json.loads(text)


def check_record(rec: dict, a_uuid: str, b_uuid: str) -> str | None:
    """Lightweight per-record sanity check before writing. Returns error or None."""
    msgs = rec.get("messages")
    if not isinstance(msgs, list) or not (4 <= len(msgs) <= 20):
        return f"bad message count: {len(msgs) if isinstance(msgs, list) else 'n/a'}"
    senders = set()
    last_t = -1
    for m in msgs:
        if m.get("sender_uuid") not in {a_uuid, b_uuid}:
            return "message sender_uuid not a participant"
        if not isinstance(m.get("text"), str) or not m["text"].strip():
            return "empty message text"
        t = m.get("t_offset_min")
        if not isinstance(t, int) or t < last_t:
            return f"bad t_offset_min sequence at {t}"
        last_t = t
        senders.add(m["sender_uuid"])
    if len(senders) < 2:
        return "only one persona spoke"
    if not isinstance(rec.get("rationale"), str) or not rec["rationale"].strip():
        return "missing rationale"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--out", default="data/conversations.jsonl")
    ap.add_argument("--seed", type=int, default=99)
    ap.add_argument("--yes-ratio", type=float, default=0.5,
                    help="Fraction of records with trigger=yes (default 0.5)")
    ap.add_argument("--resume", action="store_true",
                    help="Append to existing output instead of overwriting")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    personas = [json.loads(l) for l in PERSONAS_PATH.read_text().splitlines() if l.strip()]
    template = PROMPT_PATH.read_text()
    actions_g = json.loads(ACTIONS_PATH.read_text())
    actions_g = {k: v for k, v in actions_g.items() if not k.startswith("_")}
    reasons_g = json.loads(REASONS_PATH.read_text())
    reasons_g = {k: v for k, v in reasons_g.items() if not k.startswith("_")}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = Anthropic(api_key=api_key)

    schedule = make_label_schedule(args.count, args.yes_ratio, rng)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume else "w"

    written = 0
    skipped = 0
    with out_path.open(mode) as f:
        for target in tqdm(schedule, desc="conversations"):
            picked = sample_pair(personas, target, rng)
            if not picked:
                skipped += 1
                continue
            a, b, perspective, platform, rel = picked
            prompt = build_prompt(template, actions_g, reasons_g,
                                  a, b, perspective, platform, rel, target)
            try:
                conv = call_claude(client, prompt)
            except Exception as e:
                print(f"  call_claude error: {e}", file=sys.stderr)
                skipped += 1
                continue

            err = check_record(conv, a["uuid"], b["uuid"])
            if err:
                print(f"  record rejected ({target['trigger']}/{target.get('action') or target.get('negative_reason')}): {err}",
                      file=sys.stderr)
                skipped += 1
                continue

            record = {
                "conversation_id": str(uuid.uuid4()),
                "persona_a_uuid": a["uuid"],
                "persona_b_uuid": b["uuid"],
                "perspective_persona_uuid": perspective["uuid"],
                "relationship": rel,
                "platform": platform,
                "topic_text": conv.get("topic_text", ""),
                "messages": conv["messages"],
                "trigger": target["trigger"],
                "action": target["action"],
                "negative_reason": target["negative_reason"],
                "boundary_case": bool(conv.get("boundary_case", False)),
                "rationale": conv["rationale"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            written += 1

    print(f"Wrote {written} conversations to {out_path} (skipped {skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
