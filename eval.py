"""
Model-based (LLM-as-a-judge) evaluation of the smartphone assistant's traces.

Fetches the root "user-query" observation of each trace from Langfuse, maps it to
the question, the final answer and the context the model actually saw, scores it
with Ragas metrics, and pushes the scores back to Langfuse via
`run_batched_evaluation`.

Usage:
    uv run python eval.py                  # evaluate the 20 most recent queries
    uv run python eval.py --max-items 100
"""
import argparse
import asyncio
import json
import os

import dotenv
from langfuse import Evaluation, EvaluatorInputs, get_client
from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

dotenv.load_dotenv()

EXIT_COMMANDS = {"exit", "quit", "bye", "end"}

langfuse = get_client()

# The judge uses the same OpenAI-compatible provider configured for the app
openai_client = AsyncOpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)
judge_llm = llm_factory(os.getenv("OPENAI_MODEL"), client=openai_client)
judge_embeddings = OpenAIEmbeddings(
    client=openai_client,
    model=os.getenv("OPENAI_EMBEDDINGS_MODEL"),
)

faithfulness_metric = Faithfulness(llm=judge_llm)
answer_relevancy_metric = AnswerRelevancy(llm=judge_llm, embeddings=judge_embeddings)


# ---------------------------
# Mapper
# ---------------------------
def get_retrieved_contexts(trace_id: str) -> list[str]:
    """
    Return the SmartphoneInfo tool outputs that the final-response LLM call saw.

    The trace-level input/output only holds the question and the answer, which
    isn't enough for faithfulness. The final-response generation receives the
    whole conversation, including tool messages from earlier turns, so follow-up
    questions ("is its battery good?") are judged against the specs retrieved
    earlier in the conversation, which is the context the answer was based on.

    :param
        trace_id (str): The trace to read.

    :returns
        list[str]: The content of every tool message in the final-response input.
    """
    observations = langfuse.api.observations.get_many(
        trace_id=trace_id, fields="core,basic,io", limit=100
    ).data
    final_response_ids = {o.id for o in observations if o.name == "final-response"}
    generation = next(
        (o for o in observations
         if o.type == "GENERATION" and o.parent_observation_id in final_response_ids),
        None,
    )
    if generation is None or not generation.input:
        return []

    try:
        messages = json.loads(generation.input)
    except json.JSONDecodeError:
        return []

    return [
        m["content"] for m in messages
        if isinstance(m, dict) and m.get("role") == "tool" and m.get("content")
    ]


async def trace_mapper(*, item, **kwargs) -> EvaluatorInputs:
    """
    Map a root "user-query" observation to evaluator inputs.

    :param
        item (ObservationV2): The root observation of a trace (raw string input/output).

    :returns
        EvaluatorInputs: question as input, final answer as output, and the
        retrieved contexts in metadata.
    """
    question = (item.input or "").strip()
    contexts = []
    if question.lower() not in EXIT_COMMANDS:
        contexts = await asyncio.to_thread(get_retrieved_contexts, item.trace_id)

    return EvaluatorInputs(
        input=question,
        output=item.output or "",
        expected_output=None,
        metadata={"trace_id": item.trace_id, "retrieved_contexts": contexts},
    )


# ---------------------------
# Evaluators
# ---------------------------
def is_evaluable(question: str, answer: str) -> bool:
    """Skip goodbye traces and traces without an answer (e.g. a failed chain)."""
    return bool(question) and bool(answer) and question.lower() not in EXIT_COMMANDS


async def faithfulness_evaluator(*, input, output, expected_output, metadata, **kwargs):
    """
    Ragas faithfulness: share of claims in the answer supported by the retrieved specs.
    Skipped when nothing was retrieved (e.g. off-topic refusals), where the score
    wouldn't be meaningful.
    """
    contexts = (metadata or {}).get("retrieved_contexts") or []
    if not is_evaluable(input, output) or not contexts:
        return []

    result = await faithfulness_metric.ascore(
        user_input=input, response=output, retrieved_contexts=contexts
    )
    return Evaluation(
        name="ragas_faithfulness",
        value=float(result.value),
        comment=result.reason or f"Judged against {len(contexts)} retrieved spec sheet(s).",
    )


async def answer_relevancy_evaluator(*, input, output, expected_output, metadata, **kwargs):
    """Ragas answer relevancy: how directly the answer addresses the question."""
    if not is_evaluable(input, output):
        return []

    result = await answer_relevancy_metric.ascore(user_input=input, response=output)
    return Evaluation(
        name="ragas_answer_relevancy",
        value=float(result.value),
        comment=result.reason,
    )


# ---------------------------
# Batch evaluation
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Run Ragas evaluations on Langfuse traces.")
    parser.add_argument("--max-items", type=int, default=20,
                        help="Number of most recent user queries to evaluate (default: 20).")
    args = parser.parse_args()

    try:
        result = langfuse.run_batched_evaluation(
            mapper=trace_mapper,
            evaluators=[faithfulness_evaluator, answer_relevancy_evaluator],
            # One root observation per trace, i.e. one item per user query
            filter=json.dumps([
                {"type": "string", "column": "name", "operator": "=", "value": "user-query"}
            ]),
            max_items=args.max_items,
            max_concurrency=3,
            verbose=True,
        )

        print(f"\nProcessed {result.total_items_processed} queries, "
              f"created {result.total_scores_created} scores, "
              f"{result.total_evaluations_failed} evaluations failed.")
    finally:
        langfuse.flush()


if __name__ == "__main__":
    main()
