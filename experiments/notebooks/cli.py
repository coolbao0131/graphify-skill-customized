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
    common_kwargs = dict(
        skip_recently_updated_min=args.skip_min,
        refresh_summaries=args.refresh_summaries,
        refresh_chunk_size=args.refresh_chunk_size,
    )
    if args.update and GRAPH_PATH.exists():
        existing = load(GRAPH_PATH)
        g = build_meta_graph(existing=existing, **common_kwargs)
        new = len(g.nodes) - len(existing.nodes)
        print(f"\n✓ updated meta-graph at {GRAPH_PATH}", file=sys.stderr)
        print(f"  {len(existing.nodes)} → {len(g.nodes)} notebooks "
              f"(+{max(0, new)} new), {len(g.edges)} edges", file=sys.stderr)
    else:
        g = build_meta_graph(**common_kwargs)
        print(f"\n✓ built meta-graph from scratch at {GRAPH_PATH}", file=sys.stderr)
        print(f"  {len(g.nodes)} notebooks, {len(g.edges)} edges", file=sys.stderr)
    save(g, GRAPH_PATH)


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
    # cross_result has dataclass-ish structure; convert to plain + enrich titles
    if "cross_result" in r:
        cr = r["cross_result"]
        # Enrich notebook_title (SDK returns UUID); look up from our graph
        id_to_label = {n.notebook_id: n.label for n in g.nodes}
        for entry in cr.get("results", []):
            real_title = id_to_label.get(entry.get("notebook_id"))
            if real_title:
                entry["notebook_title"] = real_title
            if entry.get("answer") and len(entry["answer"]) > args.max_chars:
                entry["answer"] = entry["answer"][:args.max_chars] + "...(truncated)"
        r["cross_result_summary"] = {
            "queried": cr.get("notebooks_queried"),
            "succeeded": cr.get("notebooks_succeeded"),
            "failed": cr.get("notebooks_failed"),
        }
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


def cmd_inspect(args):
    g = load(GRAPH_PATH)
    print(f"Meta-graph built at: {g.built_at}", file=sys.stderr)
    print(f"Notebooks ({len(g.nodes)}):", file=sys.stderr)
    print(f"  {'srcs':>4}  {'titles':>6}  {'topics':>6}  {'summary':>7}  label", file=sys.stderr)
    for n in sorted(g.nodes, key=lambda x: -x.source_count):
        print(f"  {n.source_count:>4}  {len(n.source_titles):>6}  "
              f"{len(n.suggested_topics):>6}  {len(n.summary):>5}c  "
              f"{n.label[:50]}", file=sys.stderr)
    print(f"\nEdges ({len(g.edges)}):", file=sys.stderr)
    rel_counts = {}
    for e in g.edges:
        rel_counts[e.relation] = rel_counts.get(e.relation, 0) + 1
    for rel, c in sorted(rel_counts.items()):
        print(f"  {c:>4}  {rel}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync", help="build meta-graph from all notebooks")
    s.add_argument("--skip-min", type=int, default=5,
                   help="skip notebooks updated within last N min (still indexing)")
    s.add_argument("--update", action="store_true",
                   help="incremental: keep existing nodes whose updated_at hasn't changed, "
                        "only re-fetch new/modified notebooks")
    s.add_argument("--refresh-summaries", action="store_true",
                   help="replace each notebook's summary with a live chat.query response "
                        "(bypasses describe's source-budget bias). Slow: ~70s per chunk.")
    s.add_argument("--refresh-chunk-size", type=int, default=5,
                   help="parallel batch size for live summary refresh (default 5)")
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
    s.add_argument("--max-chars", type=int, default=2000,
                   help="truncate per-notebook answer text in output")
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("inspect", help="show graph stats")
    s.set_defaults(func=cmd_inspect)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
