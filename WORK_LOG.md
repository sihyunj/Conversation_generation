# Work Log

A running log of what Claude (the assistant) did on this repo, branch by branch.
Newest entries on top.

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
