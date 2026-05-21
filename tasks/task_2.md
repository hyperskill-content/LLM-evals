## Langfuse Monitoring

### **Table of Contents**

- [Description](#description)
- [Useful Notes](#useful-notes)
- [Development Steps](#development-steps)
- [Deliverables](#deliverables)
- [Useful Resources](#useful-resources)
    - [Topics and Projects](#topics)
    - [Docs](#docs)

### Description

Langfuse allows you to trace every LLM call and other functions in your app. You can monitor chains, agents, and others. You can track the complete execution flow for API calls, track model usage, and more. It doesn't matter if you built your app in pure Python, OpenAI SDKs, or LLM frameworks such as [LangChain](https://langfuse.com/docs/integrations/langchain/tracing) and [LlamaIndex](https://langfuse.com/docs/integrations/llama-index/get-started); Langfuse allows you to monitor all of them. Since our chatbot is built with LangChain, we will focus on that here.

### Useful Notes

Collecting metrics from LangChain applications is achieved using callbacks. **Callbacks** in LangChain allow you to perform custom actions at different phases of your LLM application. This is valuable for logging, monitoring, streaming, and more.

Don't worry, we won't be creating any callbacks from scratch. All you need to do is add Langfuse's callback handler wherever you make an LLM call:

```python
from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()
response = llm.invoke(prompt, config={"callbacks": [langfuse_handler]})
```

We're initializing a callback handler and passing it when invoking the LLM. Ensure you've set the keys and host for your Langfuse instance in your `.env` file:

```bash
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_BASE_URL="https://cloud.langfuse.com"  # or your self-hosted URL
```

That's it! Now, every time an LLM call is made, the traces will be captured by Langfuse, and you can view them in the web interface. Besides `.invoke()` methods, you can also add the callback handler to `.run()`, `.call()`, `.predict()`, `.async`, `.batch()`, and streaming interfaces in LangChain.

You can also add trace attributes such as session ID, user ID, and tags to group and identify your traces. There are two ways to do this:

**Option 1: Using metadata field in the chain invocation**

```python
response = llm.invoke(prompt, config={
	 "run_name": "my-run",
	 "callbacks": [langfuse_handler],
	 "metadata": {
	    "langfuse_session_id": "your-session-id",
        "langfuse_user_id": "hyper-user",
        "langfuse_tags": ["dev", "test"]
     },
})
```

**Option 2: Using `propagate_attributes()` context manager**

```python
from langfuse import get_client, propagate_attributes

langfuse = get_client()

with propagate_attributes(
    session_id="your-session-id",
    user_id="hyper-user",
    tags=["dev", "test"]
):
    response = llm.invoke(prompt, config={
        "run_name": "my-run",
        "callbacks": [langfuse_handler]
    })
```

Use **Option 1** when you want to set attributes per individual chain invocation. Use **Option 2** when you want attributes to automatically propagate to all operations within a scope (useful when grouping multiple operations under a single trace).

Langfuse also allows you to monitor any other function that you want. Here, you need to use the `observe` decorator:

```python
from langfuse import observe

@observe(name="hello_world")  # set run name
def hello():
	print("Hello, world!")
```

You could also use this decorator alongside the callback handler to group multiple LangChain runs into a single trace. To set trace attributes, use the `propagate_attributes` context manager as shown:

```python
from langfuse import observe, get_client, propagate_attributes

@observe() # decorator creates a trace
def hello():
  langfuse = get_client()

  # Use propagate_attributes to set trace attributes
  # These will propagate to all child observations created within this scope
  with propagate_attributes(
      trace_name="hello_world",
      session_id="my_session",
  ):
      print("Hello, world!")

  # For trace I/O (deprecated - only for backward compat with legacy trace-level LLM-as-a-judge)
  # langfuse.set_current_trace_io(input={"query": "..."}, output={"result": "..."})
```

Refer to the [documentation](https://langfuse.com/docs/get-started) for more details on monitoring LangChain applications.

### Development Steps

In this task, we need to monitor our data loader, tool invocations, and any LLM calls. Since the application processes multiple user queries in a conversation loop, each query should create its own trace for better observability. However, we want to group all traces from the same conversation session together using a `session_id`, and identify traces by `user_id`. This allows you to see individual query performance while still being able to analyze the entire conversation session.

To get a unique session/user for the conversation, you can generate them once at the start of the application:

```python
import uuid

# Generate once at startup (before the main loop)
session_id = f"session-{uuid.uuid4().hex[:8]}"
user_id = f"user-{uuid.uuid4().hex[:8]}"

# or use a predefined list of users
users = ["James", "George", "Mike", "Sherlock"]
user_id = users[uuid.uuid4().int % len(users)]
```

The same `session_id` and `user_id` should be used for all traces within that conversation, which allows Langfuse to group them together in the UI. Once the task is complete, you should see individual traces for each query, with metrics such as tokens used, cost, latency, inputs, and outputs. You can filter by session to see all queries from a single conversation.

Here's what you need to do:

- Use the `observe` decorator to monitor the data loader/vector store (`embed_documents()`) and tool calls (`generate_context()`) functions. These will create their own observations.
- Generate a unique `session_id` and `user_id` once at the start of the application (before the conversation loop begins), as shown in the example above.
- Create a Langfuse callback handler that will be used for all LangChain invocations.
- For each iteration of the conversation loop (each user query), use the `metadata` field to pass the session and user IDs to the LangChain invocations. There are 3 chain invocations per loop iteration:
  - Context chain — use run name `context` and include `langfuse_session_id` and `langfuse_user_id` in metadata;
  - Final response chain — use run name `final-response` and include the same session/user IDs in metadata;
  - Goodbye message chain (when user exits) — use run name `goodbye-message` and include the same session/user IDs in metadata.
- Each query will create its own trace, but all traces from the same conversation will share the same `session_id` for easy grouping in the Langfuse UI.
- Keep the given code mostly the same and make only the necessary additions for the above requirements.

Here are some examples of what you would see in the Langfuse UI:

Example 1: *Traces*

![Traces in Langfuse UI](../assets/images/traces.png)

Example 2: *Trace details*

![Trace details in UI](../assets/images/trace_details.png)

### Deliverables

Your code should now integrate Langfuse monitoring using both the `observe` decorator as well as the `CallbackHandler` for Langchain interfaces. When you run the code and send some queries, you should see traces in the web UI showing inputs, outputs, latency, cost, tokens, and other aspects of the app.

### **Useful Resources**

### **Topics**
- [Overview of Langfuse](https://hyperskill.org/learn/step/52531).
- [Further steps of Langfuse](https://hyperskill.org/learn/step/52629).

### **Docs**

- [Tracing for LangChain apps](https://langfuse.com/docs/integrations/langchain/tracing).
- [LangChain Runnable configuration](https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.config.RunnableConfig.html).






