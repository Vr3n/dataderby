# Slide-deck rules

**Applies to:** every deck in `docs/`, and every request that says "make a slide
deck".
**Reference decks:** `docs/whoscored-discovery-report.html` (paper/editorial),
`docs/production-readiness-slides.html` (dark technical).

The purpose of these rules is simple: a reader who was not in the room should be
able to follow the deck without the presenter explaining a single term.

## 1. Write the brief first

Before any HTML, write three sentences:

1. **The argument.** "This deck argues that ___."
2. **The audience.** Who they are, and what they already know.
3. **The takeaway.** What they should believe or do afterwards.

If the argument cannot be written in one sentence, the deck is not ready. A deck
is an argument with evidence, not a list of findings.

## 2. Give it a spine

- Pick one thing to follow: one row, one decision, one incident, one question.
- Split it into three or four acts. Each act answers a question and raises the
  next one.
- A hard problem gets **three to six slides**, never one crowded slide:
  **expected → happened → why it was silent → how it was caught → the fix →
  the proof.**
- Transitions are explicit. End an act with the question the next act answers.
- Do not include an agenda slide unless it carries a decision.

## 3. Define every term

- Define a term the first time it appears, in the sentence, or on a glossary
  page when the deck uses more than three domain terms.
- **Never** use repository shorthand without expanding it: issue numbers,
  assertion ids, command names, file names, table names.
  - Bad: "run and probe fetch the way the sweep does (#14)."
  - Good: "`dataderby run` is the command a schedule calls. It cannot fetch the
    feeds yet, because the feed only answers inside the site's browser page.
    Issue #14 tracks that change."
- If a number appears, say what it counts and in what unit: "108 feed calls:
  12 stages × 9 feeds", not "108 calls".
- Replace internal adjectives with descriptions:
  - "browser-bound" → "the feed only answers inside the site's own browser page".
  - "incoherent" → "the numbers cannot all be true at once".
- No "page N" references. Slides move; name the section instead.
- Avoid "simple", "just", "obviously", "as you know".

## 4. One idea per slide

- The headline is a **claim**, not a label.
  - Good: "A deduction is not a mistake."
  - Bad: "Points."
- One table, one diagram, or at most three short paragraphs per slide.
- Put the takeaway in the headline or the first line; do not make the reader
  infer it from a table.
- Whitespace is allowed. Crowding is not. If a slide needs a scrollbar at
  1600×900, split it.

## 5. Show, don't assert

Every claim carries an artefact:

| Claim type | Show |
|---|---|
| Scale | a big number with its unit and source |
| Change | a before/after table or a diff |
| Process | a chain diagram with the actual steps |
| Rule | the rule in code, next to the failing row |
| Missing data | the empty payload, quoted |
| Trade-off | two columns, or a verdict box |
| Sequence | a timeline with the trigger named |

Numbers must be checked against the report or the source before they go on a
slide. A deck that is off by one is worse than no deck, because it looks
authoritative.

## 6. Motion explains hierarchy

- Animate in reading order: headline lines, then the diagram, then cards, then
  table rows.
- Durations 0.3–0.9 s; stagger 0.04–0.09 s.
- Count up only numbers that matter (12 stages, 108 calls). Never animate every
  number on every slide.
- Never animate body text letter by letter.
- Respect `prefers-reduced-motion`.
- If the GSAP CDN is blocked, show the final state immediately. The deck must
  work offline.
- Motion must never hide content or delay the reader's ability to read.

## 7. Reuse a theme

Do not invent a palette per deck.

- **Paper/editorial** (`whoscored-discovery-report.html`): decisions, reviews,
  analysis for a mixed audience. Serif headlines, condensed labels, mono numbers,
  navy/red accents, 1600×900 stage.
- **Dark technical** (`production-readiness-slides.html`): engineering
  onboarding, architecture, concept teaching.
- Pick one and keep its tokens, fonts, chrome, and stage. Dark slides are for
  turning points, not for decoration.
- Keep the 1600×900 stage and scale it to the viewport; do not build a
  responsive page and call it a deck.

## 8. Presenter notes

Every slide gets a `data-note` (or equivalent) that explains the **why** in plain
words: what to say, what the audience should notice, and what not to assume.
A slide without a note is unfinished.

## 9. Verify by rendering

Structural checks are not enough. Before committing:

- [ ] Slide count and section labels are what you expect.
- [ ] No unclosed tags; the inline script passes `node --check`.
- [ ] Every slide rendered at 1600×900; nothing clipped by the footer or the
      stage edge (decorative cover art is the only exception).
- [ ] Key slides inspected as images: cover, a table, a code slide, a dark
      breaker, the close.
- [ ] Every number cross-checked against the report or source.
- [ ] Every term defined; no unexplained issue number, command, or assertion id.
- [ ] No "page N" references.
- [ ] Every slide has a presenter note.
- [ ] The deck links to its report, and the report links back.
- [ ] `docs/reports/README.md` updated when the deck is a report companion.

## 10. Red flags

Stop and rewrite when you see:

- A sentence with two acronyms and a parenthetical.
- "See #14" without saying what #14 is.
- A table with no takeaway sentence.
- A slide that only works if the presenter defines a term aloud.
- A claim with no number, quote, or artefact.
- A hardcoded page reference.
- A title slide that makes no argument.
- More than six bullets on one slide.
- A deck that reads like a changelog.

## 11. Workflow

1. Write the brief and the acts in a scratch note.
2. Outline every slide as **headline + evidence + note** before writing HTML.
3. Copy the closest reference deck's shell; keep its CSS tokens.
4. Build the slides in batches; validate structure after each batch.
5. Render every slide; fix clipped or crowded pages.
6. Re-check every number against the report.
7. Commit the deck and the report link together.

## 12. Default structure

A 20–25 slide deck usually looks like this:

| Slides | Purpose |
|---|---|
| 1 | Cover: the argument, not the title of the project |
| 2 | Why this work exists; what the previous evidence could not prove |
| 3 | Glossary: every term used later |
| 4 | Method: what was actually run, and what it is not |
| 5 | The evidence at a glance: numbers, table, or diagram |
| 6 | What held; the positive result |
| 7 | Act break for the first failure |
| 8–12 | Failure one: expected, happened, why, caught, fix, proof |
| 13 | Act break for the second failure |
| 14–17 | Failure two, same arc |
| 18 | The open item, in full: what it is, what it blocks, its id |
| 19 | What changed, as files |
| 20 | Scorecard: works vs open, with explicit sentences |
| 21 | Next, in dependency order, with names |
| 22 | Close: the lesson and the links |

## 13. File naming and links

- Deck: `docs/<topic>-slides.html`.
- Report: `docs/reports/<slug>.md` (see the Documentation section in
  `AGENTS.md`).
- The deck's close slide names the report, the commit, the test count, and the
  open issue.
- The report's References section names the deck.
- The reports index gets a row only when the deck is a companion to a report.

## 14. The one-sentence test

Before committing, read the deck from the cover to the close as a stranger.

If you have to explain a term, an abbreviation, or a number that is not on the
slide, the slide is not finished.
