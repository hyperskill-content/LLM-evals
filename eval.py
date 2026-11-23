import inspect
import json
import dotenv
from langfuse import Evaluation, EvaluatorInputs, get_client
from langfuse.batch_evaluation import BatchEvaluationRunner
from openai import AsyncOpenAI
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

dotenv.load_dotenv()
langfuse = get_client()

# Langfuse v4 OSS runs in events_only mode where legacy v1 /traces and /observations
# return 404, while /api/public/v2/observations (langfuse.api.observations.get_many) works.
_orig_fetch_batch = BatchEvaluationRunner._fetch_batch_with_retry


async def _v4_fetch_batch_with_retry(
    self,
    *,
    scope: str,
    filter: str | None,
    page: int,
    limit: int,
    max_retries: int,
    fields: str | None,
):
    if scope == "observations":
        if page > 1:
            return []
        response = self.client.api.observations.get_many(
            limit=limit,
            filter=filter,
            fields="core,basic,io",
            request_options={"max_retries": max_retries},
        )
        return list(response.data)
    return await _orig_fetch_batch(
        self,
        scope=scope,
        filter=filter,
        page=page,
        limit=limit,
        max_retries=max_retries,
        fields=fields,
    )


BatchEvaluationRunner._fetch_batch_with_retry = _v4_fetch_batch_with_retry


def _extract_text(payload) -> str:
    if isinstance(payload, dict):
        for key in ("user_input", "content", "output", "input", "text"):
            if key in payload and payload[key] is not None:
                return str(payload[key])
        return json.dumps(payload)
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if parsed is not payload:
                return _extract_text(parsed)
        except json.JSONDecodeError:
            pass
        return payload
    return str(payload) if payload is not None else ""


def _get_retrieved_contexts(trace_id: str) -> list[str]:
    contexts: list[str] = []
    if not trace_id:
        return contexts
    obs_filter = json.dumps([
        {"type": "string", "column": "traceId", "operator": "=", "value": trace_id},
        {"type": "string", "column": "name", "operator": "=", "value": "SmartphoneInfo"},
    ])
    obs_page = langfuse.api.observations.get_many(
        filter=obs_filter,
        fields="core,basic,io",
        limit=100,
    )
    for obs in getattr(obs_page, "data", []) or []:
        if getattr(obs, "name", None) == "SmartphoneInfo":
            out_text = _extract_text(getattr(obs, "output", None)).strip()
            if out_text:
                contexts.append(out_text)
    return contexts


def trace_mapper(*, item):
    """Map a Langfuse root user-query observation to EvaluatorInputs."""
    user_input = _extract_text(item.input)
    answer = _extract_text(item.output)
    retrieved_contexts = _get_retrieved_contexts(item.trace_id)

    return EvaluatorInputs(
        input=user_input,
        output=answer,
        expected_output=None,
        metadata={
            "trace_id": item.trace_id,
            "observation_id": item.id,
            "retrieved_contexts": retrieved_contexts,
        },
    )


_openai_client = AsyncOpenAI()
_llm = llm_factory("gpt-4o-mini", client=_openai_client)
_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", client=_openai_client)

faithfulness_metric = Faithfulness(llm=_llm)
relevancy_metric = AnswerRelevancy(llm=_llm, embeddings=_embeddings)


async def _score_metric(
    metric,
    *,
    user_input: str,
    response: str,
    retrieved_contexts: list[str] | None = None,
) -> float:
    if hasattr(metric, "ascore"):
        params = inspect.signature(metric.ascore).parameters
        kwargs = {
            "user_input": user_input,
            "response": response,
        }
        if "retrieved_contexts" in params:
            kwargs["retrieved_contexts"] = retrieved_contexts or []
        result = await metric.ascore(**kwargs)
    else:
        sample = SingleTurnSample(
            user_input=user_input,
            response=response,
            retrieved_contexts=retrieved_contexts or [],
        )
        result = await metric.single_turn_ascore(sample)

    return float(getattr(result, "value", result))


async def faithfulness_evaluator(*, input, output, expected_output=None, metadata=None):
    contexts = (metadata or {}).get("retrieved_contexts") or []
    if not contexts:
        return []
    score = await _score_metric(
        faithfulness_metric,
        user_input=str(input),
        response=str(output),
        retrieved_contexts=contexts,
    )
    return Evaluation(name="faithfulness", value=score)


async def answer_relevancy_evaluator(*, input, output, expected_output=None, metadata=None):
    contexts = (metadata or {}).get("retrieved_contexts") or []
    score = await _score_metric(
        relevancy_metric,
        user_input=str(input),
        response=str(output),
        retrieved_contexts=contexts,
    )
    return Evaluation(name="answer_relevancy", value=score)


def main():
    filter_json = json.dumps([
        {"type": "string", "column": "name", "operator": "=", "value": "user-query"},
        {"type": "boolean", "column": "isRootObservation", "operator": "=", "value": True},
    ])
    result = langfuse.run_batched_evaluation(
        scope="observations",
        mapper=trace_mapper,
        evaluators=[faithfulness_evaluator, answer_relevancy_evaluator],
        filter=filter_json,
        max_items=5,
        _add_observation_scores_to_trace=True,
        verbose=True,
    )
    print(result.total_items_processed, result.total_scores_created)
    langfuse.flush()


if __name__ == "__main__":
    main()