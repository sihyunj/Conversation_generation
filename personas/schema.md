# Persona Schema

Each line in `data/personas.jsonl` is one JSON object with the fields below.

## Identity

| Field | Type | Description |
|---|---|---|
| `uuid` | string | UUID4, globally unique |
| `first_name` | string | English first name |
| `last_name` | string | English/Spanish/Asian/etc. last name reflecting US demographics |
| `sex` | enum | `Male` \| `Female` (biological sex only) |
| `age` | int | 18–92 |

## Geography

| Field | Type | Description |
|---|---|---|
| `region` | enum | `Northeast` \| `Midwest` \| `South` \| `West` |
| `state` | string | US state full name (e.g., `California`) |
| `city` | string | City within the state |

## Background

| Field | Type | Description |
|---|---|---|
| `ethnicity` | enum | `White` \| `Hispanic` \| `Black` \| `Asian` \| `Multiracial` \| `Native American` |
| `native_language` | enum | `English` (English-only dataset; see project conventions) |
| `education_level` | enum | `Less than HS` \| `HS diploma` \| `Some college` \| `Associate` \| `Bachelor's` \| `Graduate` |
| `marital_status` | enum | `Single` \| `Married` \| `Divorced` \| `Widowed` \| `Cohabiting` |
| `household_size` | int | 1–7 |
| `occupation` | string | Specific occupation title |
| `income_bracket` | enum | `under_25k` \| `25-50k` \| `50-75k` \| `75-100k` \| `100-150k` \| `150k+` |

## Personality (Big Five, 0–100 scale)

| Field | Type |
|---|---|
| `openness` | int |
| `conscientiousness` | int |
| `extraversion` | int |
| `agreeableness` | int |
| `neuroticism` | int |

## Messaging traits

| Field | Type | Values | Notes |
|---|---|---|---|
| `communication_style` | enum | `formal`, `professional`, `casual`, `playful`, `terse` | Overall register |
| `emoji_density` | enum | `none`, `low`, `medium`, `high` | How often emojis appear |
| `abbreviation_use` | enum | `none`, `minimal`, `moderate`, `heavy` | "u" for "you", "lol", "rn" etc. |
| `avg_message_length` | enum | `very_short`, `short`, `medium`, `long` | Typical text length |
| `punctuation_style` | enum | `minimal`, `standard`, `expressive` | Periods, ellipses, !!!, ?? |
| `capitalization_style` | enum | `lowercase`, `sentence_case`, `proper`, `random` | Casing habits |
| `preferred_platforms` | list[enum] | `SMS`, `iMessage`, `WhatsApp`, `Slack`, `Discord`, `Instagram_DM`, `Snapchat`, `Facebook_Messenger`, `email`, `Teams`, `Telegram` | Platforms they actually use |
| `slang_register` | enum | `none`, `mild`, `moderate`, `heavy_genz`, `heavy_millennial`, `regional` | Slang intensity & generation |

### Plausibility guards

- `slang_register=heavy_genz` should not appear with age > 30
- `slang_register=heavy_millennial` typically age 28–44
- `preferred_platforms` containing `Discord`/`Snapchat` is rare for age > 55
- `email`/`Teams` likely present for white-collar or age > 40
- `capitalization_style=lowercase` correlates with younger ages and casual styles

## Narratives

| Field | Type | Description |
|---|---|---|
| `professional_persona` | string | 1–2 sentences on work life, expertise, career trajectory |
| `social_persona` | string | 1–2 sentences on social circle, personality in groups |
| `messaging_persona` | string | 1–2 sentences specifically on **how they text** (length, tone, emoji, response time, voice notes, etc.) |
| `hobbies_and_interests` | string | comma-separated or short list-y sentence |
| `core_values` | string | 1 short sentence on what they care about |

## Topics file (`data/topics.jsonl`)

Each line:

| Field | Type | Description |
|---|---|---|
| `topic_id` | string | UUID4 |
| `persona_a_uuid` | string | references `personas.jsonl` |
| `persona_b_uuid` | string | references `personas.jsonl` |
| `relationship` | enum | `friends`, `close_friends`, `family_immediate`, `family_extended`, `romantic_partner`, `dating_early`, `coworkers`, `manager_report`, `classmates`, `neighbors`, `acquaintance`, `online_friend`, `service_customer` |
| `platform` | string | platform the chat happens on (must be in both personas' `preferred_platforms`) |
| `topic` | string | conversation topic, 1 short sentence |
| `tone` | enum | `casual`, `serious`, `playful`, `tense`, `supportive`, `transactional`, `flirty`, `excited`, `professional`, `formal` |
| `opener_hint` | string | optional first-message direction for the conversation generator |

### Implausible combinations (excluded)

- Age gap > 25 years for `friends` / `close_friends` / `dating_early` / `romantic_partner` (family OK)
- `manager_report` where the younger person is the manager AND age gap > 20
- `dating_early`/`romantic_partner` between immediate family
- Platform must be in both personas' `preferred_platforms`
- `online_friend` requires both personas to use Discord, Twitter, or a similar platform
- `service_customer` only when one persona's occupation supports it (e.g., realtor, hairstylist, mechanic, barista)
- Topic must make sense given both personas' occupations / interests / age
