"""CLI wrapper for meta_graph.

Usage:
    python cli.py sync              # build meta-graph, write notebooks-graph.json
    python cli.py route "<question>" [-k 3]
    python cli.py ask "<question>" [-k 3]
    python cli.py inspect           # show meta-graph stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from meta_graph import build_meta_graph, route, ask_meta, save, load


GRAPH_PATH = Path("graphify-out/notebooks-graph.json")


def cmd_sync(args):
    g = build_meta_graph(skip_recently_updated_min=args.skip_min)
    save(g, GRAPH_PATH)
    print(f"\n✓ saved meta-graph to {GRAPH_PATH}", file=sys.stderr)
    print(f"  {len(g.nodes)} notebooks, {len(g.edges)} edges", file=sys.stderr)


def cmd_route(args):
    g = load(GRAPH_PATH)
    r = route(g, args.question, k=args.k,
              null_threshold=args.null_threshold,
              skew_threshold=args.skew_threshold)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_ask(args):
    g = load(GRAPH_PATH)
    r = ask_meta(g, args.question, k=args.k,
                 null_threshold=args.null_threshold,
                 skew_threshold=args.skew_threshold,
                 timeout=args.timeout)
    # cross_result has dataclass-ish structure; convert to plain
    if "cross_result" in r:
        cr = r["cross_result"]
        r["cross_result_summary"] = {
            "queried": cr.get("notebooks_queried"),
            "succeeded": cr.get("notebooks_succeeded"),
            "failed": cr.get("notebooks_failed"),
        }
        # truncate long answers for terminal readability
        for entry in cr.get("results", []):
            if entry.get("answer") and len(entry["answer"]) > 800:
                entry["answer"] = entry["answer"][:800] + "...(truncated)"
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


def cmd_inspect(args):
    g = load(GRAPH_PATH)
    print(f"Meta-graph built at: {g.built_at}", file=sys.stderr)
    print(f"Notebooks ({len(g.nodes)}):", file=sys.stderr)
    for n in sorted(g.nodes, key=lambda x: -x.source_count):
        print(f"  {n.source_count:>4} srcs  {len(n.suggested_topics):>2} topics  "
              f"{len(n.summary):>5}c summary  {n.label[:50]}", file=sys.stderr)
    print(f"\nEdges ({len(g.edges)}):", file=sys.stderr)
    rel_counts = {}
    for e in g.edges:
        rel_counts[e.relation] = rel_counts.get(e.relation, 0) + 1
    for rel, c in rel_counts.items():
        print(f"  {c:>4}  {rel}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync", help="build meta-graph from all notebooks")
    s.add_argument("--skip-min", type=int, default=5,
                   help="skip notebooks updated within last N min (still indexing)")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("route", help="show routing decision for a question")
    s.add_argument("question")
    s.add_argument("-k", type=int, default=3)
    s.add_argument("--null-threshold", type=float, default=0.10)
    s.add_argument("--skew-threshold", type=float, default=0.05)
    s.set_defaults(func=cmd_route)

    s = sub.add_parser("ask", help="route + fan-out cross-notebook query")
    s.add_argument("question")
    s.add_argument("-k", type=int, default=3)
    s.add_argument("--null-threshold", type=float, default=0.10)
    s.add_argument("--skew-threshold", type=float, default=0.05)
    s.add_argument("--timeout", type=float, default=120.0)
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("inspect", help="show graph stats")
    s.set_defaults(func=cmd_inspect)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
