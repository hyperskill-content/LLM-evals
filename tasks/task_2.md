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
```

Note that `trace_name` renames the entire trace, not just the observation of the function it's called in, so only set it from the function that's actually the root of the trace, like `hello()` above. If a function running as a child observation inside an already-started trace sets it, the whole trace gets renamed too. To name an individual observation, pass `name=` to `@observe()` instead.

Refer to the [documentation](https://langfuse.com/docs/get-started) for more details on monitoring LangChain applications.

### Development Steps

In this task, we need to monitor our data loader, tool invocations, and any LLM calls. Since the application processes multiple user queries in a conversation loop, each query should create its own trace for better observability (see this [guide](https://langfuse.com/faq/all/what-does-a-good-trace-look-like#what-does-a-good-trace-look-like) for what a well-structured trace looks like). However, we want to group all traces from the same conversation session together using a `session_id`, and identify traces by `user_id`. This allows you to see individual query performance while still being able to analyze the entire conversation session.

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

- Decorate both `embed_documents()` and `generate_context()` with `@observe(name="...")`, since both need their own observation, and passing an explicit name instead of relying on Langfuse's default of the function name keeps them clearly labeled in the UI.
- Generate a unique `session_id` and `user_id` once at the start of the application (before the conversation loop begins), as shown in the example above.
- Initialize the Langfuse client using `get_client()` and create a single `CallbackHandler` instance inside `main()`, after the chains (and `embed_documents()`) are defined and before the conversation loop begins, so it's reused for all LangChain invocations. Don't create these at module level: initializing them that early leaves the handler alive during the `embed_documents()` startup trace, which can leave it associated with the wrong span context for the chain calls inside the loop.
- For each iteration of the conversation loop (each user query):
  - Create a parent span using `langfuse.start_as_current_observation(as_type="span", name="user-query")` to create a single trace for that query
  - Within the parent span, use the `propagate_attributes()` context manager to set `session_id` and `user_id` for that trace and all child observations
  - Inside the `propagate_attributes()` block, invoke the chains with the callback handler and appropriate run names:
    - Context chain — use run name `context`
    - Final response chain — use run name `final-response`
    - Goodbye message chain (when user exits) — use run name `goodbye-message`
  - Set the span's `input` and `output` as you go, not both at the end of the iteration:
    - Call `span.update(input=user_input)` right after you enter the span, before invoking any chains. If a chain raises partway through the iteration, the trace still records what the user asked, since `span.update(input=..., output=...)` at the bottom of the loop body would lose both if an exception fires before it's reached.
    - Call `span.update(output=response.content)` once the final response comes back, as its own call.
    - Pass the plain string, not a dict, e.g. `span.update(input=user_input)` rather than `span.update(input={"user_input": user_input})`. Stage 5's Ragas evaluator reads the trace's input/output and calls `str()` on them, so a dict shows up as noisy text like `"{'user_input': 'compare f13...'}"` instead of the clean query string, which is worse input for the evaluator and harder to read in the UI.
- Each user query will create its own trace with all LangChain invocations as child observations, and all traces from the same conversation will share the same `session_id` for easy grouping in the Langfuse UI.
- Langfuse sends traces in the background, so a short-lived script like this one can exit before they're delivered. Add a `finally` block around the existing `try`/`except` in `main()` that calls `langfuse.flush()`, so pending traces are sent before the process ends.
- Keep the given code mostly the same and make only the necessary additions for the above requirements.

Here are some examples of what you would see in the Langfuse UI:

Example 1: *Traces*

![Traces in Langfuse UI](../assets/images/traces.png)

Example 2: *Trace details*

![Trace details in UI](../assets/images/trace_details.png)

### Deliverables

Your code should now integrate Langfuse monitoring using both the `observe` decorator as well as the `CallbackHandler` for Langchain interfaces. When you run the code and send some queries, you should see traces in the web UI showing inputs, outputs, latency, cost, tokens, and other aspects of the app.

### **Useful Resources**

### **Docs**

- [LangChain tracing integration](https://langfuse.com/docs/integrations/langchain/tracing) - Using CallbackHandler with LangChain and setting trace attributes
- [SDK instrumentation guide](https://langfuse.com/docs/observability/sdk/instrumentation) - Using the @observe() decorator and propagate_attributes() context manager
- [Sessions feature](https://langfuse.com/docs/observability/features/sessions) - Grouping traces together with session_id






