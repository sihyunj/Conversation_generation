# Conversation Record Schema

Each line in `data/conversations.jsonl` is one JSON object representing a single
multi-turn text-message conversation between two personas, plus two labels for
training an "action suggestion at end of conversation" model.

## Top-level fields

| Field | Type | Description |
|---|---|---|
| `conversation_id` | string (UUID4) | Globally unique conversation ID |
| `persona_a_uuid` | string | First participant — references `personas/data/personas.jsonl` |
| `persona_b_uuid` | string | Second participant — references `personas/data/personas.jsonl` |
| `perspective_persona_uuid` | string | The "me" persona — must equal either `persona_a_uuid` or `persona_b_uuid`. Trigger and action are labeled from this person's point of view. |
| `relationship` | enum | One of the relationship values from `personas/schema.md` |
| `platform` | enum | One of the platform values from `personas/schema.md`. MUST appear in both personas' `preferred_platforms`. |
| `topic_text` | string | One-sentence summary of what the conversation is about |
| `messages` | list[Message] | Ordered list of 4–20 messages (see below) |
| `trigger` | enum | `"yes"` \| `"no"` |
| `action` | enum or null | One of 9 action labels (see below) if `trigger=="yes"`, else `null` |
| `negative_reason` | enum or null | One of 5 negative-reason labels (see below) if `trigger=="no"`, else `null` |
| `boundary_case` | bool | `true` if this example is genuinely hard to label (annotator disagreement plausible) |
| `rationale` | string | 1–2 sentences explaining why the label fits — useful for training analysis and quality control |

## Message sub-object

| Field | Type | Description |
|---|---|---|
| `sender_uuid` | string | Must equal `persona_a_uuid` or `persona_b_uuid` |
| `text` | string | The message text, styled per the sender's `messaging_persona` |
| `t_offset_min` | int | Minutes since the first message (non-decreasing) |

## Action labels (when `trigger == "yes"`)

These are suggestions surfaced to the perspective user at the **end** of the conversation:

| Action | Meaning |
|---|---|
| `check_weather` | Open the weather app / check the forecast |
| `open_maps` | Open a maps app for directions or a location lookup |
| `order_food` | Open a food-delivery app or pick a restaurant |
| `send_gift` | Open a gifting app / e-commerce to send a present |
| `send_money` | Open a P2P payment app (Venmo, Cash App, Zelle, etc.) |
| `set_reminder` | Add a reminder / calendar event |
| `share_photo` | Open the photo library / camera to send an image |
| `take_note` | Jot something to a notes app |
| `web_search` | Open a browser / search the web |

## Negative reasons (when `trigger == "no"`)

These exist to give the model balanced and informative negative training signal:

| Reason | When it applies |
|---|---|
| `pure_chitchat` | Conversation has no actionable signal at all — purely social, emotional, or banter content |
| `action_completed_in_convo` | An action was clearly performed during the conversation; nothing left to do |
| `other_party_action` | An action is needed, but by the **other** person, not the perspective person |
| `already_resolved_elsewhere` | The action was already handled outside this conversation |
| `ambiguous_boundary` | Hard / borderline — weak / hypothetical / future-conditional action cue where reasonable annotators might disagree. Most useful for learning the decision boundary. |

## Cross-field constraints

The validator enforces all of:

- `perspective_persona_uuid in {persona_a_uuid, persona_b_uuid}`
- `persona_a_uuid != persona_b_uuid` and both exist in `personas.jsonl`
- `platform` is in both personas' `preferred_platforms`
- `len(messages) in [4, 20]`
- Every `sender_uuid` is one of the two participants
- Both participants speak at least once
- `t_offset_min` is non-decreasing across messages
- `trigger == "yes"` ⇒ `action in <9 enum>` and `negative_reason is null`
- `trigger == "no"` ⇒ `action is null` and `negative_reason in <5 enum>`

## Why these specific negative categories?

Without explicit negative subcategories, a binary trigger=yes/no model collapses
to "does the conversation mention X-related vocab?" — which fails badly on:

- conversations where the action was *already done* (model says yes, should say no)
- conversations where the *other person* should act (model says yes, should say no)
- conversations with *hypothetical* cues (model says yes, should say no for "right now")

By holding 1/5 of negatives in each of these categories, the trained model has to
learn the *temporal*, *agentive*, and *strength* features of the cue, not just
its lexical presence.
