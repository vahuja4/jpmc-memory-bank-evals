# Experiment 5 (page numbering): six months of conversations, all five customers combined

This file is a mechanical sum of the two graded reports in this folder: the pilot (customers 028 and 009, 66 questions, regraded copy) and the full run (customers 016, 033 and 017, 99 questions). 165 questions in total. The results page reports the `q8` columns (top 8 items handed to the assistant, question as written); `r8` = top 8 with a model-rephrased query, `tm` = token-matched budget, `full` = whole history, no search.

Conditions: `raw` = search the raw transcripts, `extract` = AI-written notes (consolidation off), `both` = AI notes, merged (consolidation on), `full` = whole history in the prompt.

## Accuracy by probe type (correct / questions; all MUST items conveyed, nothing forbidden asserted)

| type | raw:q8 | raw:r8 | raw:tm | extract:q8 | extract:r8 | extract:tm | both:q8 | both:r8 | both:tm | full |
|---|---|---|---|---|---|---|---|---|---|---|
| INDIRECT | 88% (53/60) | 82% (49/60) | 63% (38/60) | 98% (59/60) | 100% (60/60) | 100% (60/60) | 100% (60/60) | 98% (59/60) | 100% (60/60) | 95% (57/60) |
| STATE | 100% (40/40) | 100% (40/40) | 58% (23/40) | 92% (37/40) | 95% (38/40) | 98% (39/40) | 100% (40/40) | 98% (39/40) | 100% (40/40) | 100% (40/40) |
| BRIEF | 30% (6/20) | 20% (4/20) | 5% (1/20) | 20% (4/20) | 25% (5/20) | 85% (17/20) | 65% (13/20) | 55% (11/20) | 80% (16/20) | 95% (19/20) |
| EXACT | 100% (15/15) | 100% (15/15) | 53% (8/15) | 100% (15/15) | 87% (13/15) | 93% (14/15) | 100% (15/15) | 100% (15/15) | 100% (15/15) | 93% (14/15) |
| HISTORY | 60% (6/10) | 70% (7/10) | 20% (2/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) |
| PROMISE | 90% (9/10) | 80% (8/10) | 50% (5/10) | 90% (9/10) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) | 100% (10/10) |
| ABSENT | 100% (10/10) | 100% (10/10) | 90% (9/10) | 90% (9/10) | 90% (9/10) | 100% (10/10) | 100% (10/10) | 90% (9/10) | 100% (10/10) | 100% (10/10) |
| ALL | 84% (139/165) | 81% (133/165) | 52% (86/165) | 86% (142/165) | 87% (143/165) | 96% (159/165) | 95% (157/165) | 92% (152/165) | 97% (160/165) | 96% (159/165) |

## The four columns the page shows (q8 and full), as counts

| type | raw | extract | both | full | of |
|---|---|---|---|---|---|
| INDIRECT | 53 | 59 | 60 | 57 | 60 |
| STATE | 40 | 37 | 40 | 40 | 40 |
| BRIEF | 6 | 4 | 13 | 19 | 20 |
| EXACT | 15 | 15 | 15 | 14 | 15 |
| HISTORY | 6 | 9 | 9 | 9 | 10 |
| PROMISE | 9 | 9 | 10 | 10 | 10 |
| ABSENT | 10 | 9 | 10 | 10 | 10 |
| ALL | 139 | 142 | 157 | 159 | 165 |

MUST-item recall (mean share of MUST items conveyed, weighted 66:99 across the two runs): raw:q8 0.898, raw:r8 0.879, raw:tm 0.574, extract:q8 0.914, extract:r8 0.904, extract:tm 0.975, both:q8 0.978, both:r8 0.955, both:tm 0.984, full 0.977
