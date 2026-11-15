# Calibration: what the untouched corpus changed

The validator was written before the generator and run over the 77 shipped
Frends Processes before anything generated. Any rule that fired on a shipped
file was either wrong or belonged at warning severity. Three rules changed as a
direct result, and one real defect in the shipped material turned up.

## Rules that had to change

### `gateway-marker` — scoped to exclusiveGateway
286 of 286 exclusive gateway shapes carry `isMarkerVisible="true"`. The single
inclusive gateway in the corpus does **not**. A rule reading "a gateway shape
missing `isMarkerVisible`" therefore fires on a shipped file. Scoped to
`exclusiveGateway` as an error; left as a warning for other gateway kinds.

### `main-path-bend` — restricted to real horizontal continuations
The naive form ("a node with one predecessor should sit on its predecessor's
centre line") fired **94 times across 41 of 77 files** — more than half the
corpus. Two of its firings are not bends at all:

- containers are sized by their content, so a `subProcess` centre line
  legitimately differs from its predecessor's — 40 firings;
- Return and Throw shapes deliberately hang below the row and are entered from
  the top — 43.8% of endEvents and 98.3% of throws — 40 firings.

Restricting it to flows that actually enter the target's **left** edge leaves 3
firings, all of them genuine, and all in the same three files as the defect
below.

### `extra-waypoints` — only when the direct line is clear
Fired 4 times on the corpus. Each was a same-row hop skipping several ranks,
which *must* go around the shapes in between. Now it only fires when the direct
straight line is unobstructed and the flow detoured anyway: 1 firing.

## A real defect in the shipped public templates

Three files fail with `waypoint-off-shape`, 6 flows in total:
`Odoo_invoices_to_UBL_with_SFTP_upload`,
`Oracle_Database_SELECT_to_CSV_with_SFTP_upload`, and one more.

The geometry, confirmed by hand:

```
Odoo:   Assign Variable  bounds (2110, 292, 30, 30)  -> centre-y 307
        task neighbour   bounds (1800, 292, 100, 80) -> centre-y 332
        flow waypoints   (2210, 332) -> (2260, 332)
```

The 30×30 Assign Variable is **top-aligned** with its 100×80 neighbour — both at
y=292 — while its flows dock at the row centre, y=332. The arrow ends 25 px
below the box, in empty space. Same pattern in the Oracle file (y=160, shape
centre 175, flows at 200).

This is the shipped defect worth recognising: if the generator ever produces it,
the cause is per-rank centring rather than centring every shape on its row's
centre line. The tightened `main-path-bend` rule independently flags the same
three files, which is a useful corroboration.

## Warnings that are house style, not defects

These fire on shipped Frends files at rates consistent with the measured shares,
and are meant to.

| Rule | Corpus | Generated |
|---|---|---|
| `gateway-exit` | 20 in 17 files | 34 in 21 files |
| `extra-waypoints` | 1 | 0 |
| `gateway-marker` (inclusive) | 1 | 1 |

`gateway-exit` encodes measured shares, not absolutes: a gateway branch leaves
on the bottom 96.6% of the time when the target sits lower, on the right 98.8%
of the time on the same row, and on the top only 70.8% of the time when the
target sits higher. A convention followed by 70.8% of samples is house style; a
convention followed by every sample is a hard rule. That distinction is the
whole reason the two severities exist.

## What a clean validator run does not check

`validate.py` reported zero errors on all 77 regenerated files on the first full
run, which is exactly when to distrust it. Looking at the PNGs then found three
things no rule covers:

1. **Label collisions.** Every geometry rule works on shape bounds. Labels are
   not in the DI here at all, so a four-line Throw label overlapping the row
   below is invisible to the validator. Fixed in the generator by making row
   gaps label-aware, but the validator still cannot see it.
2. **Vertical sprawl.** Correct and readable but ugly: a tall container in band
   0 pushed every branch band hundreds of pixels down. No rule measures whether
   a diagram is compact.
3. **Ugly-but-legal routes.** A second Throw stacked under the same gateway
   forced a 6-waypoint detour over the top of the diagram. Valid geometry, bad
   picture.

All three were found by eye, none by a passing test.
