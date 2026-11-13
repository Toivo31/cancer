# Technique classifier

**Name the technique, then explain it.** The classifier reads a text, names the
manipulation technique or reasoning shortcut it finds, quotes the exact passage, and
explains in plain language *why* it counts as that technique, so the reader learns
something instead of just getting a verdict.

One engine, two taxonomies:

| Taxonomy | Texts | Used in | File |
|---|---|---|---|
| `misinformation` | Online cancer content | Hostinger *Decode the Noise* | `technique_classifier/taxonomies/misinformation.yaml` |
| `clinical_notes` | **Synthetic** patient records | AstraZeneca *Equal Care Across Finland* | `technique_classifier/taxonomies/clinical_notes.yaml` |

## Techniques

**misinformation:** `fear_appeal`, `fabricated_authority`, `loaded_language`,
`whataboutism`, `false_cure_anecdote`, `conspiracy_framing`.
Copy-paste campaigns and bot swarms are network-level signals, so they go in
`Verdict.coordination`, not in the technique list.

**clinical_notes:** `diagnostic_overshadowing`, `anchoring_premature_closure`,
`stigmatising_language`, `dismissive_no_safety_net`, `red_flag_without_action`.

Each technique has a `definition`, `cues`, a synthetic `example`, an `explanation`
template, the `evidence` needed before a flag can stand, and `not_this`, the look-alikes
that must not be flagged. The `not_this` lists are what keep precision up.

## Output format

One `Verdict` per text (`technique_classifier/schema.py`):

```json
{
  "text_id": "post-0042",
  "source_type": "online_post",
  "taxonomy": "misinformation",
  "flags": [
    {
      "technique_id": "fabricated_authority",
      "span": {"start": 0, "end": 33, "text": "A top Finnish oncologist secretly"},
      "confidence": 0.86,
      "explanation": "The post leans on an expert you cannot check. No name, publication or link is given.",
      "evidence": [
        {"type": "missing_source", "detail": "No named person, study or link anywhere in the post."}
      ]
    }
  ],
  "summary": "The claim rests on an unnamed authority and no evidence.",
  "abstain": false,
  "coordination": {"near_duplicates": 14, "accounts": 9, "burst": true, "shared_domains": ["example-cure.shop"]}
}
```

For clinical notes, `coordination` is `null`, and the evidence is usually a pathway fact:

```json
{"type": "missing_event", "detail": "No lab, imaging or referral within 60 days of the note."}
```

### Rules

- `technique_id` must be an id from the taxonomy. Anything else is rejected.
- The LLM returns only the quoted `span_text`; the code finds the offsets in the original
  text (`VERDICT_JSON_SCHEMA`). A quote that is not found verbatim is rejected, so the
  model cannot invent quotes.
- `explanation`: plain language, at most two sentences, aimed at a lay reader.
- `contradicting_source` evidence must carry a `url` (fetched live, e.g. via Oxylabs).
- `abstain: true` is a valid answer when the text is too ambiguous to judge.
- Run `validate_verdict(verdict, original_text)` on every model output.

## Measuring how often it is wrong

Labels use the same `Verdict` format. On a labelled test set, report per technique:

- **precision:** of the flags raised, how many were correct
- **recall:** of the real cases, how many were found
- **false-positive examples:** shown in the demo, not hidden

For `clinical_notes`, report the numbers **per patient group** (BMI, age, care route),
so the detector does not introduce a bias of its own.

## Ground rules

- `clinical_notes` runs on **synthetic records only**. No real patient data.
- A clinical flag means "worth a second look", not "a clinician made an error".
- Red-flag symptoms and day thresholds marked `[N]` / `[threshold source]` are
  placeholders until they are taken from Käypä hoito or the AstraZeneca mentors.
