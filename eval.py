import json
import os
import dotenv
from langfuse import get_client, Evaluation, EvaluatorInputs
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.embeddings import embedding_factory
from ragas.metrics.collections import Faithfulness, AnswerRelevancy

dotenv.load_dotenv()

langfuse = get_client()

client = AsyncOpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY")
)

llm = llm_factory(
    model=os.getenv("OPENAI_MODEL"),
    client=client
)

embedding = embedding_factory(
    model=os.getenv("OPENAI_EMBEDDINGS_MODEL"),
    client=client
)

faithfulness = Faithfulness(llm=llm)
answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embedding)


def trace_mapper(item):
    full_trace = langfuse.api.trace.get(item.id)

    retrieved_contexts = []
    for o in full_trace.observations:
        if o.type == "TOOL" and o.name == "SmartphoneInfo":
            retrieved_contexts.append(o.output["content"])

    return EvaluatorInputs(
        input=item.input,
        output=item.output,
        metadata={"retrieved_contexts": retrieved_contexts},
    )


async def check_faithfulness(*, input, output, metadata=None, **kwargs):
    context = metadata.get("retrieved_contexts")
    if not context:
        return []
    else:
        result = await faithfulness.ascore(user_input=input, response=output, retrieved_contexts=context)
        return Evaluation(name="ragas_faithfulness", value=result.value)


async def check_answer_relevancy(*, input, output, **kwargs):
    result = await answer_relevancy.ascore(user_input=input, response=output)
    return Evaluation(name="ragas_answer_relevancy", value=result.value)

if __name__ == "__main__":
    result = langfuse.run_batched_evaluation(
        scope="traces",
        mapper=trace_mapper,
        evaluators=[check_faithfulness, check_answer_relevancy],
        filter=json.dumps([{"type": "string", "column": "name", "operator": "=", "value": "user-query"}]),
        verbose=True,
    )

    print(result)

    langfuse.flush()