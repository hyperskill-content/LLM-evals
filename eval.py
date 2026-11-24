"""Evaluate recorded smartphone assistant responses with Ragas."""

import argparse
import json
import logging
import math
import os
import sys

from dotenv import load_dotenv
from langfuse import Evaluation, EvaluatorInputs, get_client
from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

logger = logging.getLogger(__name__)


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def extract_contexts(messages):
    messages = decode(messages)
    if not isinstance(messages, list):
        return []
    tool_ids = set()
    for message in messages:
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("name") == "SmartphoneInfo":
                tool_ids.add(call.get("id"))
    contexts = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        content = message.get("content")
        if message.get("tool_call_id") not in tool_ids or not isinstance(content, str):
            continue
        if content.startswith("Model: "):
            contexts.append(content)
    return contexts


def contexts_for_observation(client, item):
    if not item.trace_id:
        return []
    observations = []
    cursor = None
    while True:
        result = client.api.observations.get_many(
            trace_id=item.trace_id, cursor=cursor, limit=100, fields="core,basic,io"
        )
        observations.extend(result.data)
        cursor = result.meta.cursor
        if not cursor:
            break

    by_id = {observation.id: observation for observation in observations}
    candidates = []
    for observation in observations:
        if observation.type != "GENERATION":
            continue
        parent_id = observation.parent_observation_id
        within_final_response = False
        visited = set()
        while parent_id and parent_id not in visited and parent_id in by_id:
            visited.add(parent_id)
            parent = by_id[parent_id]
            within_final_response |= parent.name == "final-response"
            if parent.id == item.id:
                if within_final_response or observation.name == "final-response":
                    candidates.append(observation)
                break
            parent_id = parent.parent_observation_id
    if len(candidates) != 1:
        logger.warning("Observation %s has %d matching final generations", item.id, len(candidates))
        return []
    return extract_contexts(candidates[0].input)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-id", help="Evaluate one trace")
    parser.add_argument("--limit", type=int, default=20, help="Maximum observations to evaluate")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    model = os.getenv("EVAL_MODEL") or os.getenv("OPENAI_MODEL")
    embeddings_model = os.getenv("OPENAI_EMBEDDINGS_MODEL")
    if not model or not embeddings_model or not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY, OPENAI_MODEL (or EVAL_MODEL), and OPENAI_EMBEDDINGS_MODEL are required")

    client = get_client()
    openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_BASE_URL") or None)
    llm = llm_factory(model, client=openai)
    embeddings = embedding_factory("openai", model=embeddings_model, client=openai)
    faithfulness = Faithfulness(llm=llm)
    relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
    skipped = {"faithfulness": 0, "answer_relevancy": 0}

    def mapper(*, item):
        question = decode(item.input)
        if isinstance(question, dict):
            contexts = question.get("retrieved_contexts")
            question = question.get("user_input")
        else:
            contexts = None
        if not isinstance(contexts, list):
            try:
                contexts = contexts_for_observation(client, item)
            except Exception:
                logger.exception("Could not retrieve context for observation %s", item.id)
                contexts = []
        return EvaluatorInputs(input=question, output=decode(item.output), metadata={"retrieved_contexts": contexts, "observation_id": item.id})

    async def evaluate_faithfulness(*, input, output, expected_output, metadata):
        contexts = metadata["retrieved_contexts"]
        if not isinstance(input, str) or not input.strip() or not isinstance(output, str) or not output.strip() or not contexts:
            skipped["faithfulness"] += 1
            logger.info("Skipping faithfulness for %s: missing input, output or context", metadata["observation_id"])
            return []
        result = await faithfulness.ascore(user_input=input, response=output, retrieved_contexts=contexts)
        if not math.isfinite(result.value):
            skipped["faithfulness"] += 1
            logger.info("Skipping faithfulness for %s: no score", metadata["observation_id"])
            return []
        return Evaluation(name="faithfulness", value=float(result.value))

    async def evaluate_relevancy(*, input, output, expected_output, metadata):
        if not isinstance(input, str) or not input.strip() or not isinstance(output, str) or not output.strip():
            skipped["answer_relevancy"] += 1
            logger.info("Skipping relevancy for %s: missing input or output", metadata["observation_id"])
            return []
        result = await relevancy.ascore(user_input=input, response=output)
        if not math.isfinite(result.value):
            skipped["answer_relevancy"] += 1
            logger.info("Skipping relevancy for %s: no score", metadata["observation_id"])
            return []
        return Evaluation(name="answer_relevancy", value=float(result.value))

    filters = [{"type": "string", "column": "name", "operator": "=", "value": "user-query"}]
    if args.trace_id:
        filters.append({"type": "string", "column": "traceId", "operator": "=", "value": args.trace_id})
    try:
        result = client.run_batched_evaluation(
            mapper=mapper,
            evaluators=[evaluate_faithfulness, evaluate_relevancy],
            filter=json.dumps(filters), max_items=args.limit, verbose=True,
        )
        print(f"Processed: {result.total_items_processed}; scores: {result.total_scores_created}; "
              f"failed items: {result.total_items_failed}; failed evaluations: {result.total_evaluations_failed}")
        print(f"Skipped faithfulness: {skipped['faithfulness']}; skipped relevancy: {skipped['answer_relevancy']}")
        if not result.completed or result.total_items_failed or result.total_evaluations_failed:
            logger.error("Batch evaluation did not complete successfully: %s", result.error_summary)
            return 1
    finally:
        client.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
