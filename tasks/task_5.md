### Model-based Evaluation

### **Table of Contents**

- [Description](#description)
- [Useful Notes](#useful-notes)
- [Development Steps](#development-steps)
- [Deliverables](#deliverables)
- [Useful Resources](#useful-resources)
  - [Docs](#docs)

### Description

So far, we have utilized "human-as-a-judge" evaluations from user feedback and manual annotation to determine how the app performs. Unfortunately, manually annotating large datasets is time-consuming and costly. Additionally, users may not always provide feedback. Model-based evaluations address this by using LLMs as judges to run automated evaluations on datasets. This is also known as LLM-as-a-judge evaluation.

### Useful Notes

The evaluation of LLM-powered applications has matured significantly. The focus has moved beyond traditional metrics such as BLEU and ROUGE, which were inherited from machine translation and text summarization. While useful for measuring lexical overlap, these older metrics fall short because they cannot distinguish between a factually correct answer and one that is simply worded similarly to a reference text. They fail to assess the two most critical aspects of modern apps:

- The quality of the retrieved information.
- Whether the generated answer is factually grounded in that information.

This shortcoming has driven a shift towards modular evaluation, where the retrieval and generation components are diagnosed separately with more sophisticated, meaning-focused metrics. Frameworks like [Ragas](https://docs.ragas.io/en/stable/) and [DeepEval](https://deepeval.com/docs/evaluation-introduction) make this modern approach seamless by employing a suite of metrics designed to provide a granular and actionable assessment. Follow the inline links to learn more about each metric and the details of how they are calculated.

To evaluate the retriever, Ragas uses metrics like [context precision](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_precision/) to measure the relevance of the retrieved passages. [Context recall](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_recall/) then verifies that all necessary information was fetched. It can even drill down to [context entities recall](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_entities_recall/) for fact-heavy queries and assess how often a system makes errors with [noise sensitivity](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/noise_sensitivity/).

For the generation phase, it moves far beyond simple text similarity. [Faithfulness](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/) directly tackles the problem of hallucination by verifying that every statement in the generated answer is supported by the provided context. Meanwhile, [response relevancy](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/answer_relevance/) ensures the answer is not just faithful but also on-topic and directly addresses the user's query.

Furthermore, as systems evolve into more complex agentic systems that can utilize tools, the scope of evaluation must expand accordingly. [Tool call accuracy](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/agents/#tool-call-accuracy) evaluates whether the appropriate tool for a given task was selected and that the correct parameters were supplied for each tool call.

### Development Steps

Start by exploring the built-in UI evaluators to see how Langfuse handles LLM-as-a-judge out of the box. First, make sure you’re running the latest version of Langfuse:

```bash
docker compose up --pull always
```

Then, add an LLM connection that will be used to run evaluations. You can do so from Project Settings > LLM Connections. Next, [set up your LLM-as-a-judge pipeline](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge) from the UI:

![Setting up an Evaluator](../assets/images/setting_up_an_evaluator.png)

Ensure that variables are mapped correctly to avoid false analysis:

![Variable mapping](../assets/images/variable_mapping.png)

When you click `Execute`, and wait for a bit, you should now see the scores and comments from the model in the UI (this is a run in progress):

![Eval scores](../assets/images/eval_scores.png)

You can add and experiment with as many evaluators as you want.

If the UI covers your needs, you can stop here. Consider an external evaluation pipeline when you need more control over when traces get evaluated (e.g. scheduled runs or webhook triggers), flexibility beyond what the UI supports, version-controlled evaluation logic, or the ability to use existing evaluation frameworks like Ragas.

**Code-based evaluation**

The UI evaluators are limited to what Langfuse ships. For custom metrics, Langfuse exposes `run_batched_evaluation` in the SDK — it fetches all traces in the project, passes each one through a mapper function you define, calls your async evaluator functions, and pushes the scores back automatically.

There are three things to implement:

- A `trace_mapper` that extracts the fields you want to evaluate from each trace (e.g. `input`, `output`) and wraps them in `EvaluatorInputs`
- One or more async evaluator functions that receive those fields and return an `Evaluation` with a name and a numeric score
- A call to `run_batched_evaluation` wiring them together

Use [Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) for the metrics and the [Langfuse + Ragas cookbook](https://langfuse.com/guides/cookbook/evaluation_of_rag_with_ragas) as a reference. When you implement faithfulness, pay attention to what `retrieved_contexts` should contain and whether what's available at the trace level is sufficient for the metric to be meaningful.

### Deliverables

Implement `eval.py` with a `run_batched_evaluation` pipeline using at least two Ragas metrics and submit it as part of your PR. Scores from the run should be visible in Langfuse under the evaluated traces.

### **Useful Resources**

### **Docs**

- [LLM-as-a-judge evaluation](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [Scores via SDK](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk)
- [Ragas Metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- [Custom evals with Ragas](https://langfuse.com/guides/cookbook/evaluation_of_rag_with_ragas)