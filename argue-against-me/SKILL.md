---
name: argue-against-me
description: Structured academic debate — Claude adopts an opposing position (from named historiographical schools or disciplinary counter-positions) and challenges your thesis through formal rounds with adjustable intensity. Produces a scorecard, revised thesis, and bibliography gap analysis. Use when stress-testing arguments, preparing for peer review, or strengthening a thesis before publication.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# Argue Against Me

A structured devil's advocate for academic arguments. State your thesis, and Claude will systematically challenge it across formal debate rounds — drawing from historiographical traditions or disciplinary counter-positions — then deliver a scorecard, a stronger revised thesis, and suggestions for filling evidence gaps.

## When to Use

- You're developing an argument and want to find its weak points before a reviewer does
- You want to test whether your evidence actually supports your claim
- You need to anticipate objections for a paper, dissertation chapter, or conference presentation
- You want to explore how your thesis looks from a specific intellectual tradition
- You're stuck and want an adversarial conversation to sharpen your thinking

## Arguments

All arguments are optional.

| Argument | Values | Default |
|----------|--------|---------|
| `intensity` | `gentle`, `firm`, `ruthless` | `firm` |
| `rounds` | any integer | `3` |
| `school` | free text (e.g., "revisionist", "Marxist historiography", "postcolonial") | auto-selected: strongest opposing tradition for humanities; strongest disciplinary counter-position otherwise |

### Intensity Levels

**gentle** — Points out gaps and asks probing questions. Challenges weak evidence and logical gaps. Good for early-stage ideas you're still forming.

**firm** — Direct challenges with counterevidence. Challenges all claims, methodology, and source selection. The default — appropriate for arguments you believe are solid.

**ruthless** — Assumes nothing is established. Attacks everything including framing, definitions, periodization, and unstated assumptions. Use when preparing for hostile peer review or defending a controversial thesis.

## How It Works

### Starting a Debate

After invoking the skill, state your thesis. Optionally provide:
- Supporting evidence or sources
- The context (paper, dissertation, conference talk)
- Any specific concerns you want tested

### Round Structure

Each round follows this cycle:

```
Round N of M
─────────────
1. YOU:    State or defend your position
2. CLAUDE: Attack (challenge the argument)
3. YOU:    Rebut
4. CLAUDE: Per-round assessment (brief verdict before next round)
```

**Round 1 is special.** Claude's opening attack will:
- Declare the opposing school or lens it's adopting, and why it's the strongest counter-position
- Identify the 2-3 strongest lines of attack against your thesis

**Subsequent rounds** build on the exchange. Claude escalates, introduces new counterevidence, or shifts angle when you successfully rebut a point. Claude does not repeat defeated arguments.

### Mid-Debate Commands

At any point during the debate, you can say:

- **extend** — add more rounds beyond the original count
- **resolve** — end the debate early and skip to the closing output
- **concede [point]** — acknowledge a specific point to narrow the remaining debate

### Closing Output

After the final round (or when you say `resolve`), Claude produces three things:

#### 1. Scorecard

A table assessing each claim you made:

| Claim | Held? | Strength (1-5) | Notes |
|-------|-------|-----------------|-------|
| ... | ✓/✗/△ | ... | ... |

- ✓ = held up under challenge
- ✗ = dismantled
- △ = partially held (survived with qualifications)

Strength is scored using the rubric in `references/scoring_rubric.md`.

Followed by an overall verdict paragraph.

#### 2. Revised Thesis

A rewritten version of your original thesis that:
- Drops claims that were dismantled
- Adds qualifications where you made partial concessions
- Preserves what survived intact
- Notes what changed and why

#### 3. Bibliography Gaps

Specific suggestions for strengthening your argument:
- Sources you'd need to address the counterarguments raised
- Primary sources that could fill evidentiary gaps
- Methodological frameworks that could shore up weak points
- Where relevant, suggests using other skills to find sources:
  - Library catalogs (Columbia CLIO, Harvard, HathiTrust, LOC, NLB Singapore)
  - Biographical databases (CBDB, JBDB)
  - Wikidata for linked data and identifiers
  - arXiv for relevant preprints
  - Zotero for managing found references

## Best Practices

- **State your thesis clearly up front.** A vague thesis produces vague attacks. The more specific your claim, the more useful the challenge.
- **Bring your evidence.** If you have sources, cite them. Claude will attack the evidence, not just the logic — but only if you provide it.
- **Don't concede too easily.** The skill is most useful when you genuinely defend your position. Push back.
- **Use `ruthless` before submission.** If your argument survives ruthless intensity, it's ready for peer review.
- **Try different schools.** Run the same thesis against multiple traditions to find blind spots you didn't expect.

## Example

```
User: /argue-against-me intensity=firm rounds=3

My thesis: The Song dynasty's commercial revolution (960-1279) was primarily
driven by state policy — particularly the monetization reforms and the
relaxation of market regulations — rather than by endogenous economic forces
or technological change.

I'm supporting this with evidence from the expansion of government-issued
currency, the abolition of the ward-market system, and state investment in
canal infrastructure.
```

Claude would:
1. Select an opposing lens (likely quantitative/cliometric or world-systems theory)
2. Attack the state-primacy framing — e.g., arguing that demographic growth, iron production advances, and Southeastern Asian trade networks preceded and enabled state reforms
3. Challenge the evidence — e.g., questioning whether currency expansion was state-led or a response to existing commercial demand
4. Run 3 rounds of structured debate
5. Produce scorecard, revised thesis, and bibliography gaps
```

**Step 2: Do NOT commit.** Just create the file. The controller will handle commits.
