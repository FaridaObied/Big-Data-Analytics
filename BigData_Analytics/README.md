# Mini MapReduce Engine

**Student:** Farida Obied  
**Course:** CIS4103 · Big Data Analytics — Lecture 06  
**Assignment:** Bonus — Build Your MapReduce (5 marks)

---

## What it does

A word-count MapReduce engine written in Python from scratch.  
No Hadoop. No Spark. Every phase is hand-built.

Comes with two ways to run it: a command-line tool and an interactive Streamlit dashboard.

---

## Pipeline

```
input/*.txt  (one file = one split)
    │
    ├─ [1] Map       — tokenize each split, lowercase + strip punctuation
    ├─ [2] Combine   — count words locally per split (built into the mapper)
    ├─ [3] Partition — route each word: sum(ord(c) for c in word) % 2
    ├─ [4] Shuffle & Sort — group by word across all mappers, sort alphabetically
    └─ [5] Reduce    — sum counts, write output/reducer_0.txt + reducer_1.txt
```

Mappers run in **parallel threads**, one per split.  
The partition is **deterministic**: the same word always goes to the same reducer.

---

## Files

| File | Purpose |
|---|---|
| `engine.py` | Core MapReduce logic (all 5 phases) |
| `main.py` | Command-line interface |
| `app.py` | Streamlit dashboard |
| `input/` | Three ETI claim note splits |
| `output/` | Generated at runtime |

---

## How to run

### Option A — Command line

```bash
python main.py
# or with custom paths:
python main.py --input input/ --output output/ --reducers 2
```

### Option B — Streamlit dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Sample input (3 ETI claim notes)

```
claim_1.txt:  car fire car damage
claim_2.txt:  water roof water damage
claim_3.txt:  car theft water damage
```

## Sample output

**output/reducer_0.txt**
```
car     3
fire    1
roof    1
```

**output/reducer_1.txt**
```
damage  3
theft   1
water   3
```

Total words: 3 + 1 + 1 + 3 + 1 + 3 = **12** — exactly the 12 tokens we started with.