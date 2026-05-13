# External Messaging-Style Dataset Sources

The `seed_messages.jsonl` file in this folder is a small **curated** set of single-turn
example messages, hand-written to cover the persona styles in `personas.jsonl`. If you
need substantially more real-world or realistic-synthetic messaging data to fine-tune
or pre-train a conversation model, the public datasets below are good starting points.

> **Note**: every dataset has its own license and ethical use rules. Always check the
> dataset card / license before fine-tuning or redistributing. We did not redistribute
> any of these here — only documented their existence and how they relate to this project.

## Recommended starting points

| Dataset | Style | License | Why it's useful |
|---|---|---|---|
| [`daily_dialog`](https://huggingface.co/datasets/daily_dialog) | Open-domain English dialog with emotion + dialog-act labels (~13k convs) | CC BY-NC-SA 4.0 | Casual everyday conversation; act/emotion labels useful for tone-controlled generation. |
| [`empathetic_dialogues`](https://huggingface.co/datasets/empathetic_dialogues) | ~25k empathetic conversations, each conditioned on a feeling | CC BY-NC 4.0 | Pairs well with our `supportive` and `tense` topic pairs. |
| [`AlekseyKorshuk/persona-chat`](https://huggingface.co/datasets/AlekseyKorshuk/persona-chat) | Persona-grounded English dialogue | MIT | Same persona-based generation pattern; smaller and simpler personas than ours. |
| [`MultiWOZ_2.2`](https://huggingface.co/datasets/multi_woz_v22) | Task-oriented conversations (booking, info) | MIT | Maps to our `transactional`/`service_customer` slice. |
| [SMS Spam Collection (UCI)](https://archive.ics.uci.edu/dataset/228/sms+spam+collection) | 5.5k real SMS messages (spam + ham, English) | Open | Real SMS register: lengths, abbreviations. The non-spam half is the useful part. |
| [NUS SMS Corpus](https://github.com/kite1988/nus-sms-corpus) | 67k+ real SMS (English + Chinese) collected at NUS | CC BY-SA | Singapore-leaning, but the English subset has authentic abbrevs/emoji. |
| [`zhongkaifu/dialog_data` / DSTC variants](https://huggingface.co/datasets) | Dialog State Tracking Challenge corpora | varies | Useful for grounded multi-turn conversation. |
| [`Hello-SimpleAI/HC3`](https://huggingface.co/datasets/Hello-SimpleAI/HC3) | Human vs ChatGPT comparison answers | CC BY-SA 4.0 | Distinguishing human vs LLM register, not pure chat. |
| [Reddit conversations](https://convokit.cornell.edu/) (via ConvoKit) | Subreddit-derived dialog | varies | Good for less-formal, internet-native English; needs filtering. |
| [Twitter Customer Support](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) | ~3M tweets between brands and customers | Open | Pairs well with `service_customer`. |
| [`vicgalle/alpaca-gpt4`](https://huggingface.co/datasets/vicgalle/alpaca-gpt4) | Synthetic instruct (not chat) | CC BY-NC 4.0 | Mostly out of scope, but useful as instruction-style data. |

## Synthetic / persona-pretraining datasets

- **NVIDIA Nemotron-Personas** — the inspiration for this project. Comes in regional
  flavors: [Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea),
  [USA](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA),
  [Japan](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Japan),
  [Singapore](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore),
  [France](https://huggingface.co/datasets/nvidia/Nemotron-Personas-France).
  All CC BY 4.0. The USA dataset can be used directly to scale beyond our 100 personas.
- **PersonaHub** (Tencent) — 1B+ synthetic personas, mostly profession-driven. Less
  rich on demographics than Nemotron-Personas-USA.

## What we'd recommend for downstream messaging fine-tuning

A reasonable corpus mix for fine-tuning a conversational model on US messaging style:

1. **Persona conditioning**: 100 personas in this repo (our `personas.jsonl`).
2. **Conversation seeds**: 91 topic-pair scenarios in `topics.jsonl`, each expanded
   into a multi-turn dialog by the conversation generator (the next stage of this repo).
3. **Style anchors**: 66 single-turn examples in `seed_messages.jsonl` to anchor the
   generator on US-English messaging conventions across age/platform/style.
4. **External corpus mix-in (optional)**: 5-15% empathetic_dialogues (for emotional
   range), 5-10% MultiWOZ (for transactional crispness), 5-10% NUS-SMS English
   subset (for SMS-register authenticity).
5. **Hold-out eval set**: a small (50-100) hand-written set of held-out US-English
   chats covering messaging traits the model needs to nail.

## Things to watch out for

- **Time drift**: slang dates fast. `heavy_genz` register in 2026 will not match 2030.
- **Platform conflation**: a 2018-era SMS corpus is not the same register as modern
  iMessage. Tag your data with platform if you can.
- **PII**: NUS-SMS, Twitter customer support, and Reddit corpora can leak PII. Run
  detection before fine-tuning.
- **License compatibility**: MultiWOZ and SMS-Spam are OK for commercial; DailyDialog
  and EmpatheticDialogues are non-commercial only.
