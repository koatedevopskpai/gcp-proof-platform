"""RAGAS scoring, ported from `ai-platform-proof`.

Scores are **reported, never used to gate**. The gate is deterministic (see main.py); these
numbers exist to be read, compared with the AWS run, and traced.

Version note (ragas 0.4.4) — carried over from the AWS module because it decides what the code
may import:

* ``ragas.metrics.collections`` holds the "modern" metrics. They are ``BaseMetric`` instances and
  ``evaluate()`` rejects them ("All metrics must be initialised metric objects").
* ``ragas.metrics`` still exports the legacy singletons, which *are* ``Metric`` instances.
* Those need the deprecated ``LangchainLLMWrapper`` / ``LangchainEmbeddingsWrapper``.

So the working path on 0.4.4 is legacy metrics plus deprecated wrappers. Both are pinned;
migrating to the collections API should be one deliberate change against a later version.
"""
from __future__ import annotations

import time
from typing import Sequence

from evaluator.contract import METRIC_NAMES


def build_adapters(judge_model: str, base_url: str, api_key: str, embedding_model: str):
    """Judge and embedding adapters for the legacy metric path."""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    chat = ChatOpenAI(model=judge_model, api_key=api_key, base_url=base_url, temperature=0)
    embeddings = OpenAIEmbeddings(model=embedding_model, api_key=api_key, base_url=base_url)
    return LangchainLLMWrapper(chat), LangchainEmbeddingsWrapper(embeddings)


def build_metrics():
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    # answer_relevancy normally generates `strictness` candidates and averages them. The LangChain
    # wrapper returns one generation, so ragas warns and silently scores one sample. Setting it to
    # 1 states what actually happens.
    answer_relevancy.strictness = 1

    return [faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness]


def score(
    rows: Sequence[dict],
    *,
    judge_model: str,
    judge_base_url: str,
    judge_api_key: str,
    embedding_model: str,
) -> dict:
    """Score rows of {case_id, question, contexts, answer, reference}.

    Missing metrics are null rather than omitted, so a column that disappears after a version bump
    is visible instead of quietly absent.
    """
    from ragas import EvaluationDataset, SingleTurnSample, evaluate

    started = time.time()
    samples = [
        SingleTurnSample(
            user_input=row["question"],
            retrieved_contexts=list(row["contexts"]),
            response=row["answer"],
            reference=row["reference"],
        )
        for row in rows
    ]
    dataset = EvaluationDataset(samples=samples)

    llm, embeddings = build_adapters(judge_model, judge_base_url, judge_api_key, embedding_model)
    metrics = build_metrics()

    # evaluate() does not return judge usage; the callback is the only place it is visible.
    try:
        from langchain_community.callbacks import get_openai_callback

        with get_openai_callback() as callback:
            result = evaluate(dataset, metrics=metrics, llm=llm, embeddings=embeddings,
                              raise_exceptions=False, show_progress=False)
        usage = {
            "prompt_tokens": callback.prompt_tokens,
            "completion_tokens": callback.completion_tokens,
            "total_tokens": callback.total_tokens,
            "total_cost_usd": round(float(callback.total_cost), 6),
            "successful_requests": callback.successful_requests,
        }
    except ImportError:
        result = evaluate(dataset, metrics=metrics, llm=llm, embeddings=embeddings,
                          raise_exceptions=False, show_progress=False)
        usage = None

    frame = result.to_pandas()
    per_sample = []
    for position, (_, record) in enumerate(frame.iterrows()):
        entry = {"case_id": rows[position]["case_id"] if position < len(rows) else str(position)}
        for name in METRIC_NAMES:
            value = record.get(name)
            entry[name] = None if value is None or value != value else round(float(value), 4)
        per_sample.append(entry)

    aggregate = {}
    for name in METRIC_NAMES:
        if name in frame.columns:
            series = frame[name].dropna()
            aggregate[name] = round(float(series.mean()), 4) if len(series) else None
        else:
            aggregate[name] = None

    return {
        "per_sample": per_sample,
        "aggregate": aggregate,
        "usage": usage,
        "metric_names_returned": sorted(str(c) for c in frame.columns if c in METRIC_NAMES),
        "duration_seconds": round(time.time() - started, 1),
    }
