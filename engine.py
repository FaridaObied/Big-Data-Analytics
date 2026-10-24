import os
import threading
from collections import defaultdict


# ── Phase 1 + 2: Map & Combine ────────────────────────────────────────────────

def map_fn(split_path: str) -> list[tuple[str, int]]:
    """
    Read one split (text file) and count every word locally.
    Combine is built in: we sum counts per word before returning,
    so we never emit raw (word, 1) pairs across the network.
    """
    local_counts: dict[str, int] = defaultdict(int)
    with open(split_path, encoding="utf-8") as f:
        for line in f:
            for token in line.split():
                word = token.lower().strip(".,!?;:\"'()-")
                if word:
                    local_counts[word] += 1
    return list(local_counts.items())


def run_mappers(splits: list[str]) -> list[list[tuple[str, int]]]:
    """Launch one thread per split. Each runs map_fn independently."""
    results: list = [None] * len(splits)

    def worker(i: int, path: str):
        results[i] = map_fn(path)

    threads = [threading.Thread(target=worker, args=(i, s))
               for i, s in enumerate(splits)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return results


# ── Phase 3: Partition ────────────────────────────────────────────────────────

def partition(word: str, num_reducers: int = 2) -> int:
    """
    Deterministic routing: sum of ASCII values modulo num_reducers.
    The same word always lands on the same reducer, every run.
    """
    return sum(ord(c) for c in word) % num_reducers


# ── Phase 4: Shuffle & Sort ───────────────────────────────────────────────────

def shuffle_and_sort(
    map_outputs: list[list[tuple[str, int]]],
    num_reducers: int = 2
) -> list[list[tuple[str, list[int]]]]:
    """
    1. Collect all (word, count) pairs from every mapper.
    2. Route each word to its reducer bucket via partition().
    3. Group all counts under the same word key.
    4. Sort each bucket alphabetically.
    """
    buckets: list[dict[str, list[int]]] = [
        defaultdict(list) for _ in range(num_reducers)
    ]
    for pairs in map_outputs:
        for word, count in pairs:
            buckets[partition(word, num_reducers)][word].append(count)

    return [sorted(b.items()) for b in buckets]


# ── Phase 5: Reduce ───────────────────────────────────────────────────────────

def reduce_fn(
    groups: list[tuple[str, list[int]]],
    reducer_id: int,
    output_dir: str
) -> list[tuple[str, int]]:
    """Sum all counts per word. Write one output file per reducer."""
    os.makedirs(output_dir, exist_ok=True)
    results = [(word, sum(counts)) for word, counts in groups]
    with open(f"{output_dir}/reducer_{reducer_id}.txt", "w") as f:
        for word, total in results:
            f.write(f"{word}\t{total}\n")
    return results


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run(input_dir: str, output_dir: str, num_reducers: int = 2) -> dict:
    """
    Run the full pipeline and return a stats dict so the
    CLI and Streamlit app can both display results.
    """
    splits = sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith(".txt")
    )
    if not splits:
        raise FileNotFoundError(f"No .txt files found in '{input_dir}'")

    # Map + Combine (parallel threads)
    map_outputs = run_mappers(splits)

    # Partition + Shuffle & Sort
    reducer_inputs = shuffle_and_sort(map_outputs, num_reducers)

    # Reduce
    final: dict[int, list[tuple[str, int]]] = {}
    for rid, groups in enumerate(reducer_inputs):
        final[rid] = reduce_fn(groups, rid, output_dir)

    return {
        "splits":          [os.path.basename(s) for s in splits],
        "map_outputs":     map_outputs,
        "reducer_inputs":  reducer_inputs,
        "results":         final,
    }