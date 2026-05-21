## Collecting User Feedback

### **Table of Contents**

- [Description](#description)
- [Useful Notes](#useful-notes)
- [Development Steps](#development-steps)
- [Deliverables](#deliverables)
- [Useful Resources](#useful-resources)
  - [Docs](#docs)

### Description

Now, we have an application that helps users choose a good smartphone on our site. In addition, we can now see how the application is performing: the cost of each LLM call, the number of tokens used, latency, and other metrics. But, how can we evaluate the correctness, relevance, and precision of the responses our chatbot is giving? This is why we need to add evaluation to RAG applications.

Here, we’d like to assess how effectively the system retrieves and integrates external knowledge, as well as the accuracy of generated responses. This will help us understand strengths, pinpoint weaknesses, and improve our chatbot.

There are various evaluation methods that we could use to assess how well an LLM application is performing. We could collect user feedback, perform manual annotation of traces, or perform model-based evaluations (LLM-as-a-judge) using frameworks such as [Ragas](https://docs.ragas.io/en/stable/) and [DeepEval](https://docs.confident-ai.com/docs/getting-started). We’ll delve into all these approaches for the remainder of the project.

### Useful Notes

Regardless of the method you use, Langfuse uses a scoring system to store the values you get after running the evaluations (along with optional comments). Scores could be numeric, categorical, or boolean. Scores are associated with a particular trace. To learn more about scores, check out the [documentation.](https://langfuse.com/docs/scores/data-model)

Once you've determined the type of scores you would like to use, the next step is to run evaluations. This would involve collecting feedback or running model-based evaluations. For now, let's focus on user feedback:

```python
feedback = input("Was this answer helpful? (Yes/No): ")
user_comment = input("Please give us a reason for your answer. This will help us improve: ")
```

Of course, in a production environment, this might be collected via UI buttons and input fields. Finally, we need to send the scores to Langfuse.

Since we're evaluating the entire conversation (not just a single query), we should use **session-level scoring**. This is the recommended approach for conversational applications where user satisfaction spans multiple interactions. Here's how to score at the session level:

```python
from langfuse import get_client

langfuse = get_client()

# Score the entire conversation session
langfuse.create_score(
    session_id=session_id,  # The session ID used throughout the conversation
    name="conversation_usefulness",
    value=feedback,
    data_type="CATEGORICAL",
    comment=user_comment
)
```

You should see the user feedback in the UI for that session, aggregated across all traces in the conversation:

![Trace score in Langfuse UI](../assets/images/score_in_langfuse_ui.png)

Once you see the user feedback, you can click on the session in the UI to see all the traces (individual queries) that were part of the conversation, along with their inputs and outputs. This helps you understand the ratings and make informed decisions.

**Why session-level scoring?** Session-level scores are particularly valuable for conversational applications because:
- User satisfaction often spans multiple interactions, not just a single query
- You can evaluate the overall conversation quality and multi-turn interaction effectiveness
- All individual traces remain visible for debugging, but feedback applies to the whole conversation

Regardless of how you collect user feedback or the evaluations you run, the flow is similar:
- Collect feedback/run evaluations;
- Push the scores to Langfuse at the appropriate level (trace, observation, or session).

In the next stages, we'll see how to perform annotation and run model-based evaluations using Ragas.

### Development Steps

When the user exits the conversation (input is "exit", "quit", "bye", or "end"), collect feedback to find out if the overall conversation was helpful. Use a rating system of Yes/No and ask users to provide a comment. Then, send the scores to Langfuse at the **session level**.

Since task_2 already sets up a `session_id` that's shared across all queries in the conversation, you can use that same `session_id` to score the entire conversation:

```python
from langfuse import get_client

langfuse = get_client()

# ... in your conversation loop ...

if user_input.lower() in ["exit", "quit", "bye", "end"]:
    goodbye_message = goodbye_chain.invoke(...)
    print(f"System: {goodbye_message.content}")

    # Collect feedback about the entire conversation
    feedback = input("Was this conversation helpful? (Yes/No): ")
    user_comment = input("Please give us a reason for your answer. This will help us improve: ")

    # Score at the session level (not individual trace)
    langfuse.create_score(
        session_id=session_id,  # Use the session_id from the start of the conversation
        name="conversation_usefulness",
        value=feedback,
        data_type="CATEGORICAL",
        comment=user_comment
    )

    break
```
### Deliverables

Your code should now collect user feedback and send it to Langfuse at the session level. When you run the code, have a conversation with multiple queries, then exit:
- You should see the session-level score in the Langfuse UI
- The score will be associated with the session, showing feedback for the entire conversation
- All individual traces (queries) from that conversation will be grouped under the same session
- You can view the session in the UI to see all traces and understand the context behind the feedback

### **Useful Resources**

### **Docs**

- [Scores via API/SDK](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk) - Shows all scoring methods including session-level scoring.
- [Sessions in Langfuse](https://langfuse.com/docs/observability/features/sessions) - Explains how sessions group multiple traces together.
- [How to evaluate sessions/conversations](https://langfuse.com/faq/all/evaluating-sessions-conversations) - Best practices for evaluating conversational applications.
- [Evaluation data model](https://langfuse.com/docs/evaluation/scores/data-model) - Understanding the scores data model.