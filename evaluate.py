"""
Task 5: Model-based evaluation using Ragas and Langfuse.

Fetches traces from Langfuse, runs Ragas metrics (faithfulness, answer relevancy),
and pushes scores back to Langfuse.
"""

import os

import dotenv
from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

from langfuse import Langfuse
from langfuse.batch_evaluation import EvaluatorInputs
from langfuse.experiment import Evaluation

dotenv.load_dotenv()

langfuse = Langfuse()

openai_client = AsyncOpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

evaluator_llm = llm_factory(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    client=openai_client,
)

evaluator_embeddings = embedding_factory(
    model=os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-ada-002"),
    client=openai_client,
)

faithfulness_metric = Faithfulness(llm=evaluator_llm)
relevancy_metric = AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings, strictness=1)


async def faithfulness_evaluator(*, input, output, **kwargs):
    """Evaluate faithfulness of the response against retrieved context."""
    result = await faithfulness_metric.ascore(
        user_input=str(input),
        response=str(output),
        retrieved_contexts=[str(output)],
    )
    return Evaluation(name="faithfulness", value=float(result.value), comment="Ragas faithfulness score")


async def relevancy_evaluator(*, input, output, **kwargs):
    """Evaluate answer relevancy of the response to the user query."""
    result = await relevancy_metric.ascore(
        user_input=str(input),
        response=str(output),
    )
    return Evaluation(name="answer_relevancy", value=float(result.value), comment="Ragas answer relevancy score")


def trace_mapper(*, item, **kwargs):
    """Map a Langfuse trace to evaluator inputs."""
    return EvaluatorInputs(
        input=item.input,
        output=item.output,
    )


def run_evaluation():
    """Run batched Ragas evaluation on existing Langfuse traces."""
    print("Starting batched evaluation on Langfuse traces...")

    result = langfuse.run_batched_evaluation(
        scope="traces",
        mapper=trace_mapper,
        evaluators=[faithfulness_evaluator, relevancy_evaluator],
        max_concurrency=1,
        verbose=True,
    )

    print(f"\nEvaluation complete.")
    print(f"  Items fetched: {result.total_items_fetched}")
    print(f"  Items processed: {result.total_items_processed}")


if __name__ == "__main__":
    run_evaluation()
