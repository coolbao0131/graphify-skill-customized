"""graphify meta-graph over NotebookLM notebooks — MVP.

Treats each NotebookLM notebook as a graphify node. Builds a meta-graph
where nodes carry summary + topics + source-titles, and routing is done
via character-ngram TF-IDF + cosine similarity (RouterRetriever-style
training-free centroid).

Includes R3AG null gate (skip query if max cosine < threshold) and
SkewRoute fallback (low score skewness → mark as low-confidence).

Dependencies:
- notebooklm_tools (the nlm CLI's underlying SDK)
- Python stdlib only otherwise (no numpy, sklearn, torch).

Usage from Python:
    from meta_graph import build_meta_graph, route, ask_meta, save, load
    g = build_meta_graph()
    save(g, "graphify-out/notebooks-graph.json")
    g = load("graphify-out/notebooks-graph.json")
    routing = route(g, "How does GraphRAG differ from vector RAG?")
    answer = ask_meta(g, "How does GraphRAG differ from vector RAG?")
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# notebooklm_tools is provided by the nlm CLI install
from notebooklm_tools.cli.utils import get_client
from notebooklm_tools.services import notebooks as nb_svc
from notebooklm_tools.services import cross_notebook as xn_svc


# ---------- TF-IDF in pure stdlib ----------

NGRAM_SIZE = 4  # character 4-grams; handles Chinese + English without tokenizer


def _ngrams(text: str, n: int = NGRAM_SIZE) -> list[str]:
    """Lowercased character n-grams. Chinese single chars also count."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    if len(text) < n:
        return [text] if text else []
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def _tf(tokens: list[str]) -> dict[str, float]:
    c = Counter(tokens)
    total = sum(c.values()) or 1
    return {t: f / total for t, f in c.items()}


def _idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """IDF = log(N / df). Smoothed."""
    N = len(corpus_tokens)
    df: Counter[str] = Counter()
    for toks in corpus_tokens:
        for t in set(toks):
            df[t] += 1
    return {t: math.log((N + 1) / (1 + d)) + 1 for t, d in df.items()}


def _tfidf(text: str, idf: dict[str, float]) -> dict[str, float]:
    toks = _ngrams(text)
    if not toks:
        return {}
    tf = _tf(toks)
    return {t: f * idf.get(t, 0.0) for t, f in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Sparse cosine on dicts."""
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------- Meta-graph data model ----------

@dataclass
class NotebookNode:
    id: str                        # "nb_<notebook_id>"
    notebook_id: str
    label: str
    summary: str
    suggested_topics: list[str]
    source_titles: list[str]
    source_count: int
    updated_at: str
    centroid_text: str = ""        # combined text used for TF-IDF
    centroid_tfidf: dict[str, float] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    relation: str
    confidence: str
    confidence_score: float
    weight: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetaGraph:
    nodes: list[NotebookNode]
    edges: list[Edge]
    idf: dict[str, float]          # corpus IDF, needed for query embedding
    built_at: str

    def get(self, node_id: str) -> NotebookNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None


# ---------- Build ----------

def _safe_describe(client, nb_id: str, retries: int = 2) -> dict:
    """describe_notebook with retry for transient failures."""
    for attempt in range(retries):
        try:
            return nb_svc.describe_notebook(client, nb_id)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  warn: describe failed for {nb_id[:8]}: {e}", file=sys.stderr)
                return {}
            time.sleep(1)
    return {}


def _safe_get(client, nb_id: str) -> dict:
    try:
        return nb_svc.get_notebook(client, nb_id)
    except Exception as e:
        print(f"  warn: get_notebook failed for {nb_id[:8]}: {e}", file=sys.stderr)
        return {}


# Prompt used to get a "live" summary that bypasses NotebookLM's describe source budget.
LIVE_SUMMARY_PROMPT = (
    "Write a 200-word summary covering ALL main topics, methods, and key "
    "concepts present across your sources. Be comprehensive — explicitly name "
    "any technique, framework, model, tool, place, or person mentioned. No "
    "introduction; go straight into the topic list."
)


def _live_summaries(client, nb_ids: list[str], chunk_size: int = 5,
                    timeout: float = 120.0, retry_individual: bool = True) -> dict[str, str]:
    """Use cross_notebook_query in chunks to fetch fresh summaries in parallel.

    Each notebook receives the LIVE_SUMMARY_PROMPT; result is the answer text.
    Returns {notebook_id: summary_text}. Failed ones return empty string.
    Estimated cost: ~70s per chunk of 5 notebooks.

    retry_individual: if True, after batched run, retry failed notebooks one-by-one
        via chat.query (no parallelism, but no chunk timeout shared with others).
    """
    out: dict[str, str] = {}
    total_chunks = (len(nb_ids) + chunk_size - 1) // chunk_size
    for i in range(0, len(nb_ids), chunk_size):
        chunk = nb_ids[i:i + chunk_size]
        chunk_idx = i // chunk_size + 1
        print(f"  [refresh] chunk {chunk_idx}/{total_chunks} "
              f"({len(chunk)} notebooks)...", file=sys.stderr)
        t0 = time.time()
        try:
            res = xn_svc.cross_notebook_query(
                client=client,
                query_text=LIVE_SUMMARY_PROMPT,
                notebook_names=chunk,
                max_concurrent=len(chunk),
                timeout=timeout,
            )
            for entry in res.get("results", []):
                nid = entry.get("notebook_id", "")
                if entry.get("error"):
                    print(f"    err {nid[:8]}: {entry['error']}", file=sys.stderr)
                    out[nid] = ""
                else:
                    out[nid] = entry.get("answer", "") or ""
            print(f"    {len([1 for n in chunk if out.get(n)])}/{len(chunk)} "
                  f"summaries in {time.time()-t0:.1f}s", file=sys.stderr)
        except Exception as e:
            print(f"    chunk failed: {e}", file=sys.stderr)
            for nid in chunk:
                out[nid] = ""

    if retry_individual:
        from notebooklm_tools.services import chat as chat_svc
        failed = [nid for nid in nb_ids if not out.get(nid)]
        if failed:
            print(f"  [refresh] retrying {len(failed)} failed individually "
                  f"(chat.query, sequential)...", file=sys.stderr)
            for nid in failed:
                try:
                    t0 = time.time()
                    res = chat_svc.query(client, nid, LIVE_SUMMARY_PROMPT, timeout=timeout)
                    ans = res.get("answer") or ""
                    if ans:
                        out[nid] = ans
                        print(f"    + {nid[:8]} recovered in {time.time()-t0:.1f}s",
                              file=sys.stderr)
                except Exception as e:
                    print(f"    - {nid[:8]} still failed: {e}", file=sys.stderr)
    return out


def build_meta_graph(
    *,
    skip_recently_updated_min: int = 5,
    max_workers: int = 4,
    existing: MetaGraph | None = None,
    refresh_summaries: bool = False,
    refresh_chunk_size: int = 5,
) -> MetaGraph:
    """Fetch all notebooks, build meta-graph nodes + edges + IDF.

    skip_recently_updated_min: skip notebooks updated within last N min
        (still indexing on NotebookLM side; cross-query may timeout).
    existing: if provided, reuse nodes whose updated_at hasn't changed.
        Only re-fetch new or modified notebooks. Edges + IDF are always
        recomputed (cheap, depend on whole corpus).
    refresh_summaries: after fetching describe, REPLACE summary with a live
        chat.query response that bypasses NotebookLM's describe source budget.
        Slow (~70s per chunk_size notebooks via cross_notebook_query) but
        produces richer, more comprehensive summaries — recommended for
        notebooks with >50 sources or after bulk source ingestion.
    refresh_chunk_size: parallel batch size for live summary refresh.
        Higher = faster but more risk of timeout. 5 is safe.
    """
    client = get_client()
    nb_list = nb_svc.list_notebooks(client)
    nbs = nb_list.get("notebooks", []) if isinstance(nb_list, dict) else nb_list

    print(f"[build] {len(nbs)} notebooks total", file=sys.stderr)

    # Filter: skip empty + recently updated
    now = time.time()
    skip_threshold = skip_recently_updated_min * 60
    eligible = []
    for nb in nbs:
        if (nb.get("source_count") or 0) == 0:
            print(f"  skip empty: {nb.get('title','(untitled)')[:30]}", file=sys.stderr)
            continue
        # updated_at parsing: ISO 8601
        ts = nb.get("updated_at", "")
        try:
            from datetime import datetime
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            if now - t < skip_threshold:
                print(f"  skip recently-updated (<{skip_recently_updated_min}min): "
                      f"{nb.get('title','')[:30]}", file=sys.stderr)
                continue
        except Exception:
            pass
        eligible.append(nb)

    print(f"[build] {len(eligible)} eligible after filter", file=sys.stderr)

    # Incremental: split into reusable vs needs-fetch
    reusable: list[NotebookNode] = []
    if existing is not None:
        old_by_id = {n.notebook_id: n for n in existing.nodes}
        still_eligible_ids = {nb["id"] for nb in eligible}
        to_fetch = []
        for nb in eligible:
            old = old_by_id.get(nb["id"])
            # reuse if updated_at unchanged AND title unchanged
            if (old and old.updated_at == nb.get("updated_at", "")
                    and old.label == (nb.get("title", "") or "(untitled)")[:200]):
                reusable.append(old)
            else:
                to_fetch.append(nb)
        dropped = [n for nid, n in old_by_id.items() if nid not in still_eligible_ids]
        if dropped:
            print(f"  dropped {len(dropped)} notebooks no longer eligible: "
                  f"{[d.label[:25] for d in dropped[:5]]}", file=sys.stderr)
        print(f"[update] reusing {len(reusable)} unchanged, fetching {len(to_fetch)} new/modified",
              file=sys.stderr)
        eligible = to_fetch

    # Parallel fetch describe + get_notebook for source titles
    nodes: list[NotebookNode] = []

    def fetch(nb):
        desc = _safe_describe(client, nb["id"])
        detail = _safe_get(client, nb["id"])
        # NotebookLM returns summary as a list of paragraph strings
        summary_raw = desc.get("summary", "") or ""
        if isinstance(summary_raw, list):
            summary = "\n\n".join(str(s) for s in summary_raw)
        else:
            summary = str(summary_raw)
        # SuggestedTopic objects come back as dicts with 'text' or as nested lists
        topics_raw = desc.get("suggested_topics", []) or desc.get("topics", []) or []
        topics: list[str] = []
        for t in topics_raw:
            if isinstance(t, dict):
                topics.append(str(t.get("text", t.get("title", ""))))
            elif isinstance(t, list):
                topics.append(" ".join(str(x) for x in t))
            else:
                topics.append(str(t))
        # source titles from detail
        srcs = detail.get("sources", []) if isinstance(detail, dict) else []
        source_titles = []
        for s in srcs:
            t = s.get("title")
            if isinstance(t, str) and t:
                source_titles.append(t[:200])
            elif isinstance(t, list):
                source_titles.append(" ".join(str(x) for x in t)[:200])
        return NotebookNode(
            id=f"nb_{nb['id']}",
            notebook_id=nb["id"],
            label=nb.get("title", "")[:200] or "(untitled)",
            summary=summary[:5000],          # cap
            suggested_topics=topics[:20],
            source_titles=source_titles[:50],
            source_count=nb.get("source_count", len(source_titles)),
            updated_at=nb.get("updated_at", ""),
        )

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch, nb): nb for nb in eligible}
        for fut in as_completed(futures):
            try:
                node = fut.result()
                # combined text for centroid
                node.centroid_text = " ".join([
                    node.label,
                    node.summary,
                    " ".join(node.suggested_topics),
                    " ".join(node.source_titles),
                ])
                nodes.append(node)
                print(f"  + {node.label[:40]:<40} "
                      f"({node.source_count} srcs, "
                      f"{len(node.summary)}c summary, "
                      f"{len(node.suggested_topics)} topics)", file=sys.stderr)
            except Exception as e:
                nb = futures[fut]
                print(f"  err: {nb.get('title','?')}: {e}", file=sys.stderr)

    # Merge incremental: reusable nodes + freshly fetched
    nodes = reusable + nodes

    # Optional: refresh summaries via chat.query for richer / unbiased coverage
    if refresh_summaries and nodes:
        print(f"[refresh] requesting live summaries for {len(nodes)} notebooks "
              f"(chunks of {refresh_chunk_size}, ~70s/chunk)...", file=sys.stderr)
        live = _live_summaries(client, [n.notebook_id for n in nodes],
                               chunk_size=refresh_chunk_size)
        replaced = 0
        for n in nodes:
            new_summary = live.get(n.notebook_id, "")
            if new_summary and len(new_summary) > 100:
                n.summary = new_summary[:5000]
                # Rebuild centroid_text since summary changed
                n.centroid_text = " ".join([
                    n.label, n.summary,
                    " ".join(n.suggested_topics),
                    " ".join(n.source_titles),
                ])
                replaced += 1
        print(f"[refresh] replaced {replaced}/{len(nodes)} summaries with live versions",
              file=sys.stderr)

    # Build IDF from all centroid texts (always recompute — cheap, depends on corpus)
    corpus_ngrams = [_ngrams(n.centroid_text) for n in nodes]
    idf = _idf(corpus_ngrams)

    # Compute per-node TF-IDF
    for n in nodes:
        n.centroid_tfidf = _tfidf(n.centroid_text, idf)

    # Edges (a) shared_sources
    edges: list[Edge] = []
    from itertools import combinations
    for a, b in combinations(nodes, 2):
        shared = set(a.source_titles) & set(b.source_titles)
        if shared:
            edges.append(Edge(
                source=a.id, target=b.id,
                relation="shares_sources",
                confidence="EXTRACTED", confidence_score=1.0,
                weight=len(shared) / max(1, min(a.source_count, b.source_count)),
                extra={"shared_count": len(shared), "examples": sorted(shared)[:5]},
            ))

    # Edges (b) semantic similarity via TF-IDF cosine
    for a, b in combinations(nodes, 2):
        sim = _cosine(a.centroid_tfidf, b.centroid_tfidf)
        if sim > 0.20:                       # threshold to avoid noise
            edges.append(Edge(
                source=a.id, target=b.id,
                relation="semantically_similar_to",
                confidence="INFERRED",
                confidence_score=min(0.95, max(0.55, round(sim, 2))),
                weight=sim,
            ))

    print(f"[build] {len(nodes)} nodes, {len(edges)} edges", file=sys.stderr)

    from datetime import datetime, timezone
    return MetaGraph(
        nodes=nodes, edges=edges, idf=idf,
        built_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------- Persist ----------

def save(g: MetaGraph, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "directed": False,
        "built_at": g.built_at,
        "idf": g.idf,
        "nodes": [asdict(n) for n in g.nodes],
        "edges": [asdict(e) for e in g.edges],
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def load(path: str | Path) -> MetaGraph:
    data = json.loads(Path(path).read_text())
    nodes = [NotebookNode(**n) for n in data["nodes"]]
    edges = [Edge(**e) for e in data["edges"]]
    return MetaGraph(nodes=nodes, edges=edges, idf=data["idf"], built_at=data["built_at"])


# ---------- Route ----------

def route(
    g: MetaGraph,
    question: str,
    *,
    k: int = 3,
    null_threshold: float = 0.10,    # R3AG: below this → no query
    skew_threshold: float = 0.05,    # SkewRoute: below this → low-confidence broad query
) -> dict:
    """Return routing decision: top-k notebooks + fallback flags.

    Returns dict with:
      routed_to: list of notebook_ids
      scores: list of cosine scores
      reason: human-readable explanation
      fallback: None | "use_LLM_parametric" | "global_summary_after"
    """
    q_vec = _tfidf(question, g.idf)
    if not q_vec:
        return {"routed_to": [], "scores": [], "reason": "empty query vector",
                "fallback": "use_LLM_parametric"}

    scored = [(n, _cosine(q_vec, n.centroid_tfidf)) for n in g.nodes]
    scored.sort(key=lambda x: -x[1])
    top = scored[:k]
    top_score = top[0][1] if top else 0.0

    # R3AG null gate
    if top_score < null_threshold:
        return {
            "routed_to": [],
            "scores": [],
            "reason": f"max cosine {top_score:.3f} < {null_threshold} (R3AG null gate)",
            "fallback": "use_LLM_parametric",
            "top_candidates": [(n.label, round(s, 3)) for n, s in scored[:5]],
        }

    # SkewRoute: top1 - topK gap
    skew = top[0][1] - top[-1][1] if len(top) > 1 else top_score
    if skew < skew_threshold:
        return {
            "routed_to": [n.notebook_id for n, _ in top],
            "scores": [round(s, 3) for _, s in top],
            "reason": f"low skew ({skew:.3f}), broad fan-out — answers will need LLM merge",
            "fallback": "global_summary_after",
            "labels": [n.label for n, _ in top],
        }

    return {
        "routed_to": [n.notebook_id for n, _ in top],
        "scores": [round(s, 3) for _, s in top],
        "reason": "high-confidence routing",
        "fallback": None,
        "labels": [n.label for n, _ in top],
    }


# ---------- Ask ----------

def ask_meta(
    g: MetaGraph,
    question: str,
    *,
    k: int = 3,
    null_threshold: float = 0.10,
    skew_threshold: float = 0.05,
    timeout: float = 120.0,
) -> dict:
    """Route then fan-out via cross_notebook_query."""
    routing = route(g, question, k=k,
                    null_threshold=null_threshold, skew_threshold=skew_threshold)

    if routing.get("fallback") == "use_LLM_parametric":
        return {
            "question": question,
            "routing": routing,
            "answer": None,
            "note": "No notebook scored above the null threshold. "
                    "Recommend rephrasing or answering from general knowledge.",
        }

    if not routing["routed_to"]:
        return {"question": question, "routing": routing, "answer": None,
                "note": "Routing returned no notebooks."}

    client = get_client()
    result = xn_svc.cross_notebook_query(
        client=client,
        query_text=question,
        notebook_names=routing["routed_to"],
        max_concurrent=min(5, k),
        timeout=timeout,
    )

    return {
        "question": question,
        "routing": routing,
        "cross_result": result,
        "note": "Each notebook returned its own grounded answer with citations. "
                "Merge them yourself or feed to an LLM for synthesis.",
    }
