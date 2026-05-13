# Work Log

A running log of what Claude (the assistant) did on this repo, branch by branch.
Newest entries on top.

---

## 2026-05-13 — `claude/messaging-conversations-3kLpQ7`

**Goal**: build the **generation pipeline** for labeled multi-turn messaging
conversations (no live generation run — just the code, prompts, schema, and
validators). The output dataset will be used to train an end-of-conversation
action-suggestion model.

### What got built

```
conversations/
├── README.md                       # purpose, pipeline, distribution defaults, limits
├── schema.md                       # full record schema + constraints + label semantics
├── generate_conversations.py       # main generation script via Anthropic SDK
├── validate_conversations.py       # structure + label-consistency + distribution checks
├── prompts/
│   ├── conv_template.txt           # master prompt parameterized by label
│   ├── action_triggers.json        # 9 entries — when each action is the right suggestion
│   └── negative_reasons.json       # 5 entries — what each negative subcategory must look like
├── examples/
│   └── sample_conversations.jsonl  # 3 hand-crafted records (used to test validator)
└── data/                           # (empty; populated by running generate_conversations.py)
```

### Label design

Two labels per conversation:

- `trigger`: `"yes"` | `"no"`
- `action`: one of 9 (`check_weather`, `open_maps`, `order_food`, `send_gift`,
  `send_money`, `set_reminder`, `share_photo`, `take_note`, `web_search`) or
  `null`

Plus a `negative_reason` (5-enum) when `trigger=="no"` — exists because a
naive binary classifier collapses to "did the conversation mention X-related
vocab?" and fails on three common patterns: action already performed, OTHER
party should act, hypothetical/weak cues. We dedicate one-fifth of negatives
to each:

- `pure_chitchat`
- `action_completed_in_convo`
- `other_party_action`
- `already_resolved_elsewhere`
- `ambiguous_boundary` — **highest-value** examples; decision-boundary cases.

Plus `boundary_case: bool`, `rationale: str` (1-2 sentence explanation),
`perspective_persona_uuid` (which of A/B is "me").

### Default distribution (for `--count 1000`, balanced)

```
trigger=yes  500  — split evenly across 9 actions ≈ 55-56 each
trigger=no   500  — split evenly across 5 reasons = 100 each
```

Tested `make_label_schedule(N, 0.5)` at N=100/250/1000: produces exactly
balanced counts (small remainder spread across the first few buckets).

Override via `--yes-ratio` and `--count`. Default is intentionally
**balanced**, not census-natural — the user didn't specify and balanced gives
a cleaner training signal for an initial model. Users can rebalance later.

### Pipeline

```
make_label_schedule(N) → balanced labels
  → for each target label:
      sample_pair(personas, label)  # random A,B with platform overlap + plausibility
      pick perspective ∈ {A, B}     # random
      pick platform ∈ overlap       # random
      pick relationship ∈ 13-enum   # random, filtered for age/family/etc plausibility
      build_prompt(...)             # injects personas, label, label-specific guidance
      call_claude(...)
      check_record(...)             # per-record sanity (msg count, sender, timing)
      append JSONL
```

### Plausibility filters (`plausible_pair_for_action`)

Hard:
- age gap ≤ 25 for peer / romantic
- classmates: age gap ≤ 12, neither > 70
- romantic with same last name only if age gap ≥ 30
- `online_friend` needs Discord/Instagram_DM/Snapchat/Telegram overlap
- `share_photo` needs a photo-capable platform in overlap

Soft (probabilistic reject):
- `send_money` for age > 78
- `set_reminder` for `acquaintance` relationship
- `send_gift` for `service_customer` relationship

### Decisions and tradeoffs

1. **Generation code only, no live generation**. Per user. We do not consume
   API credits for the data; the user will run the script with their own
   key.
2. **Pre-scheduled balanced labels** (vs. random). LLMs left to their own
   devices skew heavily toward "helpful/yes" — pre-determining the target
   label before generation gives a clean training signal and saves us from
   running an oracle classifier over generated text.
3. **LLM synthesizes the topic_text fresh** (vs. linking to topics.jsonl).
   topics.jsonl pairs are tied to specific personas; for random pairing we'd
   have to remap topics anyway. Simpler to let the LLM produce a topic that
   fits the chosen pair + label.
4. **Soft action-specific plausibility** instead of hard. Real-world tail
   cases (87yo grandma sending Venmo) exist. Rejection-sample most but not
   all.
5. **No KakaoTalk in the platform enum**. Inherited from personas — US-only
   scope. KakaoTalk would mean reworking the personas dataset, which is out
   of scope for this task.
6. **`examples/sample_conversations.jsonl` over `_build_seed.py`**. Only 3
   hand-crafted records, used purely as schema reference and to test the
   validator. We do NOT ship a bulk seed dataset — that's the live-API run's
   job.

### Validation result

```
$ python validate_conversations.py --examples
=== Conversations: 3 entries — OK no structural errors. ===
trigger: no=2, yes=1
action (yes): order_food
neg_reason (no): pure_chitchat, ambiguous_boundary
boundary_case=true: 1
msg counts: 4-6 mean 5.0
```

Validator catches: missing fields, bad enums, broken persona UUID refs,
perspective not a participant, platform not in both personas'
preferred_platforms, message count out of [4,20], sender UUID not a
participant, non-monotonic t_offset_min, only one persona spoke,
trigger=yes/no with mismatching action/negative_reason, missing rationale.

### Files NOT touched

- `personas/` — left intact.
- `main` branch — this work is on `claude/messaging-conversations-3kLpQ7`.
  No PR opened (user can request when ready).

### How to use this when you get an API key

```bash
cd conversations
pip install -r ../personas/requirements.txt
export ANTHROPIC_API_KEY=...
python generate_conversations.py --count 1000 --out data/conversations.jsonl
python validate_conversations.py
```

`--resume` appends to an existing JSONL — useful if the script gets
interrupted halfway through 1000 records.

### Known limitations / future improvements

- **No style-fidelity validator**. The validator checks the structure but
  not whether a 73yo retiree's messages actually look retiree-shaped. Future
  check could measure per-sender lowercase rate, emoji density, slang
  features, and compare to persona settings.
- **`ambiguous_boundary` quality is LLM-dependent**. Hand-review a sample
  after each run.
- **Topic diversity may need tuning** after first 1000-run — if the LLM
  keeps reaching for the same scenarios for a given (relationship, action),
  add explicit topic seeds in the prompt to force variety.
- **No de-duplication** between conversations. Two runs might produce nearly
  identical conversations. For larger corpora, add a simple Jaccard-based
  dedup pass.

---

## 2026-05-07 — `claude/create-messaging-personas-1BLeS`

**Goal**: build a synthetic persona dataset for English (US) messaging-style
conversation generation, modeled on NVIDIA Nemotron-Personas-Korea.

### What got built

```
personas/
├── README.md                   # purpose, schema, usage, regen instructions
├── schema.md                   # full field definitions (persona + topics)
├── requirements.txt            # anthropic, tqdm
├── generate_personas.py        # Anthropic SDK script for live regen
├── generate_topics.py          # topic-pair generator with plausibility filters
├── validate.py                 # structural + distribution + plausibility checks
├── _build_seed.py              # builds the shipped JSONL from hand-curated data
├── prompts/
│   ├── attributes_pool.json    # US Census-derived distribution weights
│   ├── persona_narrative.txt   # Claude prompt template for narrative gen
│   └── topics_prompt.txt       # Claude prompt template for topic gen
└── data/
    ├── personas.jsonl          # 100 personas
    ├── topics.jsonl            # 91 plausible persona-pair conversation seeds
    ├── seed_messages.jsonl     # 66 single-turn style anchors
    └── external_dataset_sources.md   # external corpora to scale up with
```

### Decisions and tradeoffs

1. **Simplified vs Nemotron-style PGM**: chose simplified weighted sampling. The
   shipped `attributes_pool.json` carries hand-tuned weights approximating US
   Census 2020-2024 ratios; not a true joint PGM. Documented in
   `personas/README.md` under "Limitations".
2. **US only** (not US/UK/AU mix). Per user.
3. **JSONL output** (not parquet). Per user.
4. **Auto-generation strategy**: writing `_build_seed.py` containing the 100
   personas as Python tuples + 91 topic-combos + 66 seed messages, then running
   it to produce JSONL. The user's environment did not expose
   `ANTHROPIC_API_KEY`, so we couldn't call the live API from a Python script.
   Since "Claude" was the requested generator and the assistant *is* Claude,
   the persona narratives, topic seeds, and seed-message styles were authored
   directly in this conversation and serialized via `_build_seed.py`.
   `generate_personas.py` and `generate_topics.py` remain in the repo as the
   official live-API path: setting `ANTHROPIC_API_KEY` and re-running them
   produces a fresh, larger batch with the same schema.
5. **Topic combinations**: hand-curated 91 pairs spanning all 13 relationship
   types and all 10 tones, with explicit plausibility guards (age gap, platform
   overlap, married-vs-single mismatch for romantic, etc.). Implemented in
   `generate_topics.py:is_plausible_pair`. Implausible combos like
   `family_immediate + romantic_partner` are blocked at the sampling stage.
6. **Seed messages**: 66 single-turn examples covering 11 register/tone slices
   (heavy_genz lowercase, heavy_millennial, casual, professional, formal,
   terse blue-collar, elder, bilingual Spanglish, Slack/Discord platform
   register, supportive, logistics, banter, flirty, service, group-chat,
   neutral). These are *not* dialogue datasets — they're style anchors for the
   downstream conversation generator. External corpora to scale up are listed
   in `data/external_dataset_sources.md`.
7. **Tone enum extension**: initial schema had 8 tones; during validation we
   noted 14 topic rows used `professional` / `formal` (which are genuinely
   useful for work-channel topics). Extended the enum to 10 tones rather than
   collapsing to less-accurate alternatives. Updated `schema.md`,
   `validate.py`, and `prompts/topics_prompt.txt`.

### Validation result (final)

```
Personas: 100 entries — OK no structural errors.
Topics:    91 entries — OK no errors.
Seed msgs: 66 entries (no validator yet — schema is shallow).

sex:        Female 50, Male 50
region:     South 37, Midwest 23, West 21, Northeast 19  (Census ~38/21/24/17)
ethnicity:  White 56, Hispanic 17, Black 15, Asian 8, NA 2, Multi 2
age_band:   18-24=16, 25-34=24, 35-44=18, 45-54=14, 55-64=12, 65-74=10, 75+=6
education:  Bachelor's 33, HS 22, Graduate 18, Some college 16, Associate 6, <HS 5
marital:    Married 48, Single 28, Cohab 9, Widowed 8, Divorced 7
occupation: 100/100 unique
slang:      none 29, mild 28, moderate 17, heavy_millennial 15, heavy_genz 11
platforms:  iMessage 78, email 62, SMS 52, FB Messenger 43, WhatsApp 39,
            Slack 34, Instagram 26, Snapchat 16, Discord 10
```

### Known limitations / things I'd improve given more time

- **Education slightly skewed high** (Bachelor's 33% vs Census ~24%). The
  hand-sampling didn't perfectly match the weights file. For a v2 rerun via
  the live API path, the script does honor the weights via `weighted_pick`.
- **Ethnicity slightly under on White** (56% vs 58% target) and over on Black
  (15% vs 13%) — within sampling noise for n=100.
- **Personas do not currently encode chronotype, response time, or
  read-receipt habits**, which would be useful for multi-turn realism.
  Listed as future work.
- **Seed messages have no validator** beyond JSONL parsing. A future check
  could verify that `slang_register` matches lexical features (regex for
  lowercase, abbrevs).

### Files NOT touched

- `README.md` (root) — left as-is (user didn't ask to update).
- Anything outside `personas/` or repo-level docs (this WORK_LOG.md and
  CLAUDE.md added at root).

### Commands to reproduce

```bash
# from repo root
cd personas
pip install -r requirements.txt

# rebuild from the hand-curated seed (deterministic, no API key needed)
python _build_seed.py

# OR regenerate live with Claude API (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=...
python generate_personas.py --count 100 --out data/personas.jsonl
python generate_topics.py --in data/personas.jsonl --out data/topics.jsonl --pairs 300

# validate
python validate.py
```
