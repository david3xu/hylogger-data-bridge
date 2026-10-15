# Purpose: diagnose a collapsed decision model from training and validation rows only.
import argparse
import json
import math
import os
import random
import socket
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.encode import encode
from training.records import load


def mapping_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Is the gold option really the gold candidate, and do positions leak the label?"""
    wrong, orders = 0, set()
    positions: Counter[tuple[str, str]] = Counter()
    for row in rows:
        _, _, mapping = encode(row["request"])
        orders.add(tuple(mapping.values()))
        chosen = [key for key, value in mapping.items() if value == row["gold"]]
        wrong += len(chosen) != 1
        positions[(row["split"], chosen[0])] += 1
    return {
        "gold_not_exactly_one_option": wrong,
        "distinct_candidate_orders": len(orders),
        "gold_option_counts": {f"{s}/{o}": n for (s, o), n in sorted(positions.items())},
    }


def offline_provider(folder: Path) -> Any:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def no_network(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network access is disabled during the offline reload")

    socket.socket.connect = no_network  # type: ignore[method-assign]
    from hylogger_bridge.advice.local import LocalProvider

    return LocalProvider(folder)


def probe(provider: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_gold: dict[str, list[list[float]]] = defaultdict(list)
    nll, finite, hits = 0.0, True, 0
    predicted: Counter[str] = Counter()
    every = []
    for row in rows:
        state, questions, mapping = encode(row["request"])
        out = provider.predict(state, questions)["follow_up"]
        scores = {mapping[k]: v for k, v in out["probabilities"].items()}
        finite &= all(math.isfinite(v) for v in scores.values())
        winner = mapping[out["answer"]]
        predicted[winner] += 1
        hits += winner == row["gold"]
        nll -= math.log(max(scores[row["gold"]], 1e-9))
        by_gold[row["gold"]].append([scores[k] for k in sorted(scores)])
        every.append([scores[k] for k in sorted(scores)])
    options = sorted(mapping.values())
    spread = [
        round(
            math.sqrt(
                sum((r[i] - sum(x[i] for x in every) / len(every)) ** 2 for r in every) / len(every)
            ),
            4,
        )
        for i in range(len(options))
    ]
    return {
        "rows": len(rows),
        "accuracy": round(hits / len(rows), 4),
        "mean_nll": round(nll / len(rows), 4),
        "all_probabilities_finite": finite,
        "predicted_counts": dict(predicted),
        "gold_counts": dict(Counter(r["gold"] for r in rows)),
        "options_sorted": options,
        "std_of_probability_per_option_across_rows": spread,
        "mean_probability_by_gold": {
            gold: [round(sum(v[i] for v in vs) / len(vs), 4) for i in range(len(options))]
            for gold, vs in sorted(by_gold.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train-sample", type=int, default=120)
    args = parser.parse_args()
    rows = load(args.records)
    train = [r for r in rows if r["split"] == "train"]
    validation = [r for r in rows if r["split"] == "validation"]
    sample = random.Random(0).sample(train, args.train_sample)
    prior = Counter(r["gold"] for r in train)
    entropy = -sum(n / len(train) * math.log(n / len(train)) for n in prior.values())
    provider = offline_provider(args.model)
    report = {
        "note": "Training and validation rows only; the test split is not read here.",
        "mapping": mapping_report([r for r in rows if r["split"] != "test"]),
        "train_label_prior": dict(prior),
        "train_prior_entropy_nats": round(entropy, 4),
        "uniform_entropy_nats": round(math.log(4), 4),
        "validation": probe(provider, validation),
        "train_sample": probe(provider, sample),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "mapping"}, indent=2))
    print(json.dumps(report["mapping"], indent=2))


if __name__ == "__main__":
    main()
