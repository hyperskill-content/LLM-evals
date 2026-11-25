import json
import os

import dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langfuse import Evaluation, EvaluatorInputs, get_client
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy

dotenv.load_dotenv()

langfuse = get_client()

eval_llm = LangchainLLMWrapper(
    ChatOpenAI(
        model=os.getenv("OPENAI_MODEL"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
)

eval_embeddings = LangchainEmbeddingsWrapper(
    OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-ada-002"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
)

faithfulness = Faithfulness(llm=eval_llm)
answer_relevancy = ResponseRelevancy(llm=eval_llm, embeddings=eval_embeddings)


def parse_io(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}


def get_retrieved_contexts(trace_id: str) -> list[str]:
    """Fetch observations on the same trace to collect tool outputs from SmartphoneInfo."""
    contexts: list[str] = []
    cursor = None

    while True:
        page = langfuse.api.observations.get_many(
            trace_id=trace_id,
            limit=100,
            cursor=cursor,
            fields="core,basic,io",
        )
        for obs in page.data:
            name = getattr(obs, "name", "") or ""
            out = parse_io(getattr(obs, "output", None))
            if name == "SmartphoneInfo" or "SmartphoneInfo" in name:
                if isinstance(out, str) and out.strip():
                    contexts.append(out.strip())
                elif isinstance(out, dict):
                    text = out.get("content") or out.get("output") or json.dumps(out)
                    if str(text).strip():
                        contexts.append(str(text))

        cursor = getattr(page.meta, "cursor", None)
        if not cursor:
            break

    return contexts


def trace_mapper(*, item) -> EvaluatorInputs:
    """Map a root user-query observation into EvaluatorInputs with retrieved contexts."""
    inp = parse_io(item.input)
    out = parse_io(item.output)

    user_input = inp.get("user_input") or inp.get("question") or (inp.get("text") if isinstance(inp, dict) else "") or ""
    response = out.get("response") or out.get("answer") or (out.get("text") if isinstance(out, dict) else "") or ""
    if isinstance(response, dict):
        response = response.get("content", str(response))

    contexts = get_retrieved_contexts(item.trace_id)

    return EvaluatorInputs(
        input=str(user_input),
        output=str(response),
        expected_output=None,
        metadata={
            "trace_id": item.trace_id,
            "observation_id": item.id,
            "retrieved_contexts": contexts,
        },
    )


async def faithfulness_evaluator(*, input, output, expected_output, metadata) -> Evaluation:
    contexts = (metadata or {}).get("retrieved_contexts") or []
    sample = SingleTurnSample(
        user_input=input or "",
        retrieved_contexts=contexts if contexts else [""],
        response=output or "",
    )
    score = await faithfulness.single_turn_ascore(sample)
    return Evaluation(name="faithfulness", value=float(score))


async def relevancy_evaluator(*, input, output, expected_output, metadata) -> Evaluation:
    contexts = (metadata or {}).get("retrieved_contexts") or []
    sample = SingleTurnSample(
        user_input=input or "",
        retrieved_contexts=contexts if contexts else [""],
        response=output or "",
    )
    score = await answer_relevancy.single_turn_ascore(sample)
    return Evaluation(name="answer_relevancy", value=float(score))


def main() -> None:
    filter_json = json.dumps(
        [
            {"type": "string", "column": "name", "operator": "=", "value": "user-query"},
            {"type": "boolean", "column": "isRootObservation", "operator": "=", "value": True},
        ]
    )

    result = langfuse.run_batched_evaluation(
        mapper=trace_mapper,
        evaluators=[faithfulness_evaluator, relevancy_evaluator],
        filter=filter_json,
        max_items=20,
        verbose=True,
    )

    print(f"Processed: {result.total_items_processed}")
    print(f"Scores created: {result.total_scores_created}")
    langfuse.flush()


if __name__ == "__main__":
    main()