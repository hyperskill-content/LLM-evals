import argparse
import asyncio
import json
import math
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langfuse import Evaluation, EvaluatorInputs, get_client
from langfuse.api import ObservationV2
from langfuse.batch_evaluation import BatchEvaluationResult
from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness


OBSERVATION_FILTER = json.dumps(
    [
        {
            "type": "string",
            "column": "name",
            "operator": "=",
            "value": "user-query",
        },
        {
            "type": "stringObject",
            "column": "metadata",
            "key": "evaluation_ready",
            "operator": "=",
            "value": "ready",
        },
    ]
)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def _get_metrics() -> tuple[Faithfulness, AnswerRelevancy]:
    api_key = _required_env("OPENAI_API_KEY")
    llm_model = os.getenv("RAGAS_LLM_MODEL") or _required_env("OPENAI_MODEL")
    embeddings_model = (
        os.getenv("RAGAS_EMBEDDINGS_MODEL")
        or _required_env("OPENAI_EMBEDDINGS_MODEL")
    )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    ragas_llm = llm_factory(
        llm_model,
        client=client,
        temperature=1,
        top_p=0.95,
        max_tokens=4096,
    )
    ragas_embeddings = RagasOpenAIEmbeddings(
        client=client,
        model=embeddings_model,
    )
    return (
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
    )


def _expanded_metadata(item: ObservationV2) -> dict[str, Any]:
    if not item.trace_id:
        raise ValueError(f"Observation {item.id} has no trace ID")

    client = get_client()
    response = client.api.observations.get_many(
        trace_id=item.trace_id,
        name="user-query",
        fields="metadata",
        expand_metadata="retrieved_contexts",
        limit=1,
    )
    matching_observation = next(
        (observation for observation in response.data if observation.id == item.id),
        None,
    )
    if matching_observation is None:
        raise ValueError(
            f"Could not reload observation {item.id} with expanded metadata"
        )
    metadata = matching_observation.metadata
    if not isinstance(metadata, dict):
        raise ValueError(f"Observation {item.id} has no metadata")
    return metadata


async def trace_mapper(*, item: ObservationV2) -> EvaluatorInputs:
    metadata = await asyncio.to_thread(_expanded_metadata, item)
    contexts = metadata.get("retrieved_contexts")
    if not isinstance(contexts, list) or not contexts or not all(
        isinstance(context, str) and context.strip() for context in contexts
    ):
        raise ValueError(
            f"Observation {item.id} has no valid retrieved contexts; "
            "run the app after enabling Task 5 context capture"
        )
    if not isinstance(item.input, str) or not item.input.strip():
        raise ValueError(f"Observation {item.id} has no query input")
    if not isinstance(item.output, str) or not item.output.strip():
        raise ValueError(f"Observation {item.id} has no response output")

    return EvaluatorInputs(
        input=item.input,
        output=item.output,
        metadata={
            "retrieved_contexts": contexts,
            "trace_id": item.trace_id,
            "observation_id": item.id,
        },
    )


def _score(name: str, value: float, reason: str | None = None) -> Evaluation:
    if not math.isfinite(value):
        raise ValueError(f"Ragas metric {name} returned a non-finite score")
    return Evaluation(name=name, value=value, comment=reason)


async def faithfulness_evaluator(
    *,
    input: str,
    output: str,
    metadata: dict[str, Any] | None = None,
    **_: Any,
) -> Evaluation:
    faithfulness, _ = _get_metrics()
    if metadata is None:
        raise ValueError("Faithfulness evaluation requires retrieved contexts")
    result = await faithfulness.ascore(
        user_input=input,
        response=output,
        retrieved_contexts=metadata["retrieved_contexts"],
    )
    return _score("faithfulness", result.value, result.reason)


async def answer_relevancy_evaluator(
    *,
    input: str,
    output: str,
    **_: Any,
) -> Evaluation:
    _, answer_relevancy = _get_metrics()
    result = await answer_relevancy.ascore(user_input=input, response=output)
    return _score("answer_relevancy", result.value, result.reason)


def run_evaluation(
    max_items: int | None,
    max_concurrency: int,
) -> BatchEvaluationResult:
    _required_env("LANGFUSE_PUBLIC_KEY")
    _required_env("LANGFUSE_SECRET_KEY")
    _get_metrics()

    result = get_client().run_batched_evaluation(
        mapper=trace_mapper,
        evaluators=[faithfulness_evaluator, answer_relevancy_evaluator],
        filter=OBSERVATION_FILTER,
        fields="core,basic,io,metadata",
        max_items=max_items,
        max_concurrency=max_concurrency,
        metadata={"evaluation": "ragas", "evaluation_version": "1"},
        verbose=True,
    )
    print(
        f"Evaluated {result.total_items_processed} observations; "
        f"created {result.total_scores_created} scores; "
        f"{result.total_items_failed} observations failed."
    )
    if result.total_items_failed or result.total_evaluations_failed:
        raise RuntimeError(
            f"{result.total_items_failed} observations and "
            f"{result.total_evaluations_failed} evaluator runs failed; "
            f"details: {result.error_summary}"
        )
    if not result.completed:
        raise RuntimeError(
            f"Langfuse batch evaluation did not complete; "
            f"details: {result.error_summary}"
        )
    if result.total_items_processed == 0:
        raise RuntimeError(
            "No eligible observations were evaluated. Run main.py with a query "
            "that retrieves smartphone information, then try again."
        )
    return result


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Evaluate eligible smartphone assistant observations with Ragas."
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum observations to evaluate (default: 10).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all matching observations instead of applying the default cap.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Maximum concurrent observation evaluations (default: 2).",
    )
    args = parser.parse_args()
    if args.max_items < 1:
        parser.error("--max-items must be a positive integer")
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be a positive integer")
    run_evaluation(None if args.all else args.max_items, args.max_concurrency)


if __name__ == "__main__":
    main()
