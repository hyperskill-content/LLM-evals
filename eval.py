"""
Task 5: model-based (LLM-as-a-judge) evaluation of the smartphone assistant's traces with Ragas.

Run from the LLM-evals folder:  uv run python eval.py
Langfuse must be running; the scores are written back onto each evaluated trace.
Needs the Langfuse Python SDK v5 (the Langfuse v4 server no longer serves the old trace-list endpoint).
"""
import json
import os
import warnings
from datetime import datetime, timedelta, timezone

# Ragas 0.4 warns that these metric imports move in Ragas 1.0; they still work
warnings.filterwarnings("ignore", category=DeprecationWarning)

import dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langfuse import get_client, EvaluatorInputs, Evaluation
from ragas import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy

dotenv.load_dotenv()

langfuse = get_client()

# ---------------------------
# Judge models used by Ragas
# ---------------------------
# Ragas sends prompts to this LLM to judge the app's answers (the "LLM-as-a-judge")
judge_llm = LangchainLLMWrapper(ChatOpenAI(
    model=os.getenv("OPENAI_MODEL"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
))
# Response relevancy also compares embeddings of questions, so it needs an embeddings model
judge_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(
    model=os.getenv("OPENAI_EMBEDDINGS_MODEL"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
))

faithfulness = Faithfulness(llm=judge_llm)
response_relevancy = ResponseRelevancy(llm=judge_llm, embeddings=judge_embeddings)

EXIT_WORDS = {"exit", "quit", "bye", "end"}


def as_text(value):
    """SDK v5 gives input/output as raw JSON text, e.g. '"Is the Pixel 8 Pro good?"'. Return the plain string."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, str) else value
        except json.JSONDecodeError:
            return value
    return None


def as_list(value):
    """Return a message list whether the API gave it as a list or as JSON text."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


# ---------------------------
# Mapper: observation -> EvaluatorInputs
# ---------------------------
def get_retrieved_contexts(trace_id: str) -> list[str]:
    """
    Return the SmartphoneInfo tool outputs used to answer this trace's question.

    The trace's own input/output only hold the question and the answer, so the specs
    have to come from inside the trace: the input messages of the ChatOpenAI generation
    under the `final-response` step. That message list is the whole conversation so far,
    so only the tool messages after the LAST user message belong to this question.
    """
    final_responses = langfuse.api.observations.get_many(
        trace_id=trace_id, name="final-response", fields="core,basic"
    ).data
    if not final_responses:
        return []

    generations = langfuse.api.observations.get_many(
        trace_id=trace_id,
        parent_observation_id=final_responses[0].id,
        type="GENERATION",
        fields="core,basic,io",  # input comes back as raw JSON text; as_list() parses it
    ).data
    if not generations:
        return []

    messages = [m for m in as_list(generations[0].input) if isinstance(m, dict)]
    last_user_index = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)

    return [
        str(m.get("content", ""))
        for m in messages[last_user_index + 1:]
        if m.get("role") == "tool"
    ]


def trace_mapper(*, item, **kwargs) -> EvaluatorInputs:
    """
    Called once per fetched observation by run_batched_evaluation, as mapper(item=observation).
    Only the root `user-query` span of each trace is evaluated; it holds the question and answer.
    """
    question = as_text(item.input)
    answer = as_text(item.output)

    is_query_root = item.name == "user-query" and not item.parent_observation_id
    skip = not is_query_root or not question or not answer or question.lower() in EXIT_WORDS

    return EvaluatorInputs(
        input=question,
        output=answer,
        expected_output=None,
        metadata={
            "skip": skip,
            "retrieved_contexts": [] if skip else get_retrieved_contexts(item.trace_id),
        },
    )


# ---------------------------
# Evaluators: EvaluatorInputs -> Evaluation
# ---------------------------
async def ragas_faithfulness(*, input, output, expected_output, metadata, **kwargs):
    """Share of the answer's claims that are supported by the retrieved specs (0-1)."""
    contexts = metadata["retrieved_contexts"]
    if metadata["skip"] or not contexts:
        return []  # no score: faithfulness means nothing without retrieved context

    sample = SingleTurnSample(user_input=input, response=output, retrieved_contexts=contexts)
    score = await faithfulness.single_turn_ascore(sample)
    return Evaluation(name="ragas_faithfulness", value=score,
                      comment=f"Judged against {len(contexts)} retrieved spec sheet(s)")


async def ragas_response_relevancy(*, input, output, expected_output, metadata, **kwargs):
    """How directly the answer addresses the question (0-1)."""
    if metadata["skip"]:
        return []

    sample = SingleTurnSample(user_input=input, response=output)
    score = await response_relevancy.single_turn_ascore(sample)
    return Evaluation(name="ragas_response_relevancy", value=score)


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = langfuse.run_batched_evaluation(
        mapper=trace_mapper,
        evaluators=[ragas_faithfulness, ragas_response_relevancy],
        # Only observations from user-query traces in the last 30 days
        filter=json.dumps([
            {"type": "string", "column": "traceName", "operator": "=", "value": "user-query"},
            {"type": "datetime", "column": "startTime", "operator": ">=", "value": since},
        ]),
        max_concurrency=3,
        # Scores are created on the root span; this also copies them onto the trace itself
        _add_observation_scores_to_trace=True,
        verbose=True,
    )

    print(f"Observations fetched: {result.total_items_fetched}")
    print(f"Observations processed: {result.total_items_processed}")
    print(f"Scores created:   {result.total_scores_created}")
    print(f"Evaluator errors: {result.total_evaluations_failed}")
    for stats in result.evaluator_stats:
        print(f"  {stats.name}: {stats.total_scores_created} scores, {stats.failed_runs} failures")

    langfuse.flush()
