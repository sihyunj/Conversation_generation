# Messaging Conversations

Synthetic multi-turn text conversations between US personas, **labeled with two
tags** for training an end-of-conversation action-suggestion model:

- `trigger`: `yes` or `no` — should we surface an action suggestion to "me"?
- `action`: one of 9 if `trigger=yes`, else `null`
  - `check_weather`, `open_maps`, `order_food`, `send_gift`, `send_money`,
    `set_reminder`, `share_photo`, `take_note`, `web_search`

The "me" here is the **perspective persona** — one of the two participants
designated as the user whose action we're predicting.

## What's here

```
conversations/
├── README.md                       # this file
├── schema.md                       # full record schema + constraints
├── generate_conversations.py       # main generation script (Anthropic SDK)
├── validate_conversations.py       # structural + label + distribution checks
├── prompts/
│   ├── conv_template.txt           # master prompt, parameterized by label
│   ├── action_triggers.json        # per-action grounding (9 entries)
│   └── negative_reasons.json       # per-negative-reason grounding (5 entries)
├── examples/
│   └── sample_conversations.jsonl  # 3 hand-crafted records (schema reference)
└── data/
    └── conversations.jsonl         # generated output (run script to create)
```

## Why two labels (not one binary)?

A naive binary `trigger` classifier collapses into "did the conversation mention
X-related vocab?" which fails badly on three common patterns:

1. **The action was already done** during the conversation ("I just venmo'd you" + 3 turns of small talk → no need to suggest send_money)
2. **The other person should act**, not "me" ("can YOU send me the address" → no, not for me)
3. **Hypothetical / future cues** ("I should look that up sometime" → not now)

We hold **half the dataset as negatives**, evenly split across 5 sub-categories:

| `negative_reason` | What it teaches the model |
|---|---|
| `pure_chitchat` | No actionable signal at all |
| `action_completed_in_convo` | Don't fire after the action was performed mid-convo |
| `other_party_action` | Don't fire when the OTHER person is the actor |
| `already_resolved_elsewhere` | Don't fire when "I already did it" via another channel |
| `ambiguous_boundary` | Decision-boundary cases — weak / hypothetical cues |

`ambiguous_boundary` examples are the highest-value training signal — they teach
the model the *strength* of a cue, not just its presence.

## Default distribution (configurable)

For `--count 1000`:

```
trigger=yes  500    # split evenly across 9 actions ≈ 55–56 each
trigger=no   500    # split evenly across 5 reasons = 100 each
```

Override via:
```bash
python generate_conversations.py --count 500 --yes-ratio 0.4
```

Random sampling for everything else:
- Persona pair: random from `personas/data/personas.jsonl`, filtered for
  platform overlap + plausibility for the target action / relationship.
- Perspective ("me"): random between the two participants.
- Platform: random from the pair's `preferred_platforms` overlap.
- Relationship: random from the 13-enum, filtered for plausibility.
- Topic: synthesized fresh by the LLM, conditioned on the pair + relationship + label.

## Usage

```bash
cd conversations
pip install -r ../personas/requirements.txt   # anthropic + tqdm
export ANTHROPIC_API_KEY=...

# generate 1000 conversations with default 50/50 trigger ratio
python generate_conversations.py --count 1000 --out data/conversations.jsonl

# resume an interrupted run (appends instead of overwriting)
python generate_conversations.py --count 1000 --resume

# validate (structure, label consistency, distributions)
python validate_conversations.py
python validate_conversations.py --examples   # validates examples/ folder
```

## Generation pipeline

```
                ┌───────────────────────────────────────┐
                │  make_label_schedule(N, yes_ratio)    │
                │  → balanced list of N target labels   │
                └────────────────┬──────────────────────┘
                                 │
              ┌──────────────────▼──────────────────┐
              │  For each target label:             │
              │    1. sample_pair(personas, label)  │
              │       → (A, B, perspective,         │
              │          platform, relationship)    │
              │    2. build_prompt() injects:       │
              │       - both personas (trimmed)     │
              │       - perspective uuid            │
              │       - relationship + platform     │
              │       - label-specific guidance     │
              │    3. call_claude()                 │
              │    4. check_record() — sanity       │
              │    5. write JSONL line              │
              └─────────────────────────────────────┘
```

## Plausibility filters

`generate_conversations.py:plausible_pair_for_action` enforces:

- Age gap ≤ 25 for peer / romantic relationships
- Classmates: age gap ≤ 12 and neither over 70
- Romantic with same last name only if age gap ≥ 30
- `online_friend` requires Discord / Instagram_DM / Snapchat / Telegram overlap
- `send_money` rarely sampled for personas over 78
- `share_photo` requires a photo-capable platform in overlap
- `send_gift` not sampled for `service_customer` relationships
- `set_reminder` rarely sampled for `acquaintance` relationships

These are *soft* filters — most are random rejection sampling so a few edge
cases can still appear, mimicking real-world tail behavior.

## Style fidelity

The prompt strongly enforces that each persona writes in their own voice. The
`trim_persona()` helper sends the LLM the messaging-relevant fields:

- `communication_style`, `emoji_density`, `abbreviation_use`, `avg_message_length`,
- `punctuation_style`, `capitalization_style`, `slang_register`,
- `messaging_persona` (1-2 sentence narrative of texting habits),
- `native_language` (always `English` in the current dataset).

A 22-year-old heavy_genz user and a 73-year-old formal retiree should produce
visibly different text in the same conversation.

## Reproducibility

`--seed N` makes the **schedule and sampling** deterministic, but the LLM
output itself is not deterministic. For full reproducibility re-runs, archive
the generated JSONL.

## Validating a fresh run

After generation, `validate_conversations.py` reports:

- Per-record structural errors (missing fields, bad enums, broken UUID refs,
  platform-not-in-preferred-platforms, etc.)
- Label-consistency errors (trigger=yes with negative_reason set, etc.)
- Realized distributions over trigger, action, negative_reason, platform,
  relationship, boundary_case rate, and message-count histogram.

A clean run prints `OK no structural errors.`

## Limitations

- **LLM-output is not deterministic**; even with seeds, re-runs produce
  different conversations.
- **Style fidelity has to be eyeballed** — there's no automatic check that
  the messages actually match each persona's `messaging_persona`. A future
  validator could check lexical features (lowercase rate, emoji density) per
  sender against the persona's settings.
- **`ambiguous_boundary` quality varies** — the LLM tends to swing between
  "too obvious yes" and "too obvious no". Hand-review a sample.
- **English-only, US-only**, inheriting from the personas module.
