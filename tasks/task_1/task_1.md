## **Introduction and Setup**

### **Table of Contents**

- [Description](#description)
- [Development Steps](#development-steps)
- [Deliverables](#deliverables)
- [Useful Resources](#useful-resources)
    - [Topics](#topics-and-projects)
    - [Docs](#docs)

### Description

We are going to use various tools in this project. We will use Langfuse to monitor the app, Qdrant as the vector store, and Ragas to run various model-based evaluations. [**Langfuse**](https://langfuse.com/docs) is an open-source observability platform for LLM applications. It allows you to monitor, evaluate, and debug your LLM applications. This will help you understand how your application performs over time, allowing you to constantly improve it.

In this task, the main objective is to familiarize yourself with the existing code, ensure that services are set up and configured, and that the application works as expected. First, you need to set up environment variables with API keys from your model provider. Next, ensure that Qdrant is up and running. Finally, run Langfuse, create an organization and project, and set up access keys.

### Development Steps

Currently, the app is configured to use OpenAI. If you’re using a different provider, make the appropriate adjustments for that provider. Therefore, your `.env` might look like this as shown in the `.env.sample` file:

```jsx
OPENAI_MODEL="<model>"
OPENAI_BASE_URL="<base_url>"
OPENAI_API_KEY="<API key>"
```

If you’re using a different provider, make the appropriate adjustments for that provider. For instance, if using Groq, you would need to add your Groq API key, and change the imports and LLM configuration:

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL"),
)
```

Next, you need to ensure that Qdrant is set up and running. But before that, ensure that you have [Docker](https://docs.docker.com/desktop/) installed and running. Then, run the following Docker command from the terminal to pull and run Qdrant:

```bash
# if you use PowerShell as your shell, replace backslashes (\) with backticks (`) as line seperators
docker run --restart always -d -p 6333:6333 -p 6334:6334 \
    -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
    qdrant/qdrant 
```

You may have issues if you run this command in the same folder as the `main.py` file. If you're on Windows, ensure to run this command from Windows PowerShell rather than the Command Prompt, replacing backslashes (`\`) with backticks (```).

Finally, we need to set up the environment ready for monitoring. There are various ways to work with Langfuse. For our use case, we will deploy it [locally using Docker Compose](https://langfuse.com/self-hosting/local). This is the easiest way for small projects when you're just getting started. All you need to do is clone the `git` repo and start the services:

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse

docker compose up
```

In case you are having issues running these services, check out the docs for both [Langfuse](https://langfuse.com/self-hosting/local) and  [Qdrant](https://qdrant.tech/documentation/quickstart/).

Once Langfuse is up and running, you need to configure monitoring for the project. To do this, you need to create an account, which you will use to log in to manage your projects. Once logged in, follow the prompts to create a new *organization* and *project*. Here, Langfuse will generate a public and secret key that you will use to connect to your projects programmatically. Copy these and place them in the `.env` file like below:

```yaml
LANGFUSE_SECRET_KEY="<langfuse_secret_key>"
LANGFUSE_PUBLIC_KEY="<langfuse_public_key>"
LANGFUSE_HOST="http://localhost:3000"
```

Great. Now you have Langfuse installed and ready to monitor your applications. In the next task, we will add monitoring to the app. As a check, run the `main.py` file directly and send some queries to it. Here are some examples:

Example 1: *Analysis and recommendations*

```bash
> User: I want the Samsung S24 Ultra.
100%|██████████| 1/1 [00:01<00:00,  1.28s/it]
100%|██████████| 1/1 [00:01<00:00,  1.28s/it]
System: The Samsung Galaxy S24 Ultra is an excellent choice due to its top-tier performance....
> User:
```

Example 2: *Comparisons*

```bash
> User: Great. How does the S24 Ultra compare to the 15 Pro Max?
100%|██████████| 1/1 [00:01<00:00,  1.28s/it]
100%|██████████| 1/1 [00:01<00:00,  1.21s/it]
100%|██████████| 1/1 [00:00<00:00,  1.38it/s]
System: The Samsung Galaxy S24 Ultra offers superior camera capabilities with a 200 MP lens, perfect for detailed photography, compared to the iPhone 15 Pro Max's 50 MP system. It also...
> User:
```

Example 3: *Cannot handle orders and customer support*

```bash
> User: The Ultra sounds good. Go ahead and proceed with the order.
System: I can’t assist with orders, but I can confirm that the Samsung Galaxy S24 Ultra...
> User: 
```

The greater-than symbol followed by a space (`>` ) represents the user input. Note that it's not part of the input. The output has been truncated for brevity.

### Deliverables

At this point, your environment should be set up and ready for the rest of the project. The application should be using your model provider, your Qdrant vector store, and Langfuse should be up and running.

### **Useful Resources**

### **Topics and Projects**

- [Introduction to LangChain](https://hyperskill.org/projects/514)
- [Building the naive RAG](https://hyperskill.org/projects/518)
- [Overview of Langfuse](https://hyperskill.org/learn/step/52531).
- [Further steps of Langfuse](https://hyperskill.org/learn/step/52629).

### **Docs**

- [Tool Calling](https://python.langchain.com/docs/concepts/tool_calling/)
- [LangChain Messages](https://python.langchain.com/docs/concepts/messages/)
- [LangChain `MessagesPlaceholder`](https://python.langchain.com/api_reference/core/prompts/langchain_core.prompts.chat.MessagesPlaceholder.html)