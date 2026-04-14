# Building LLM Apps: Evaluation

## Table of Contents

- [Introduction](#introduction)
- [Setup](#setup)
- [Learning Outcomes](#learning-outcomes)
- [Project Structure](#project-structure)
- [Tasks](#tasks)
    - [Task One — Introduction and Setup](./tasks/task_1.md)
    - [Task Two — Tracing and Monitoring](./tasks/task_2.md)
    - [Task Three — Collecting User Feedback](./tasks/task_3.md)
    - [Task Four — Annotation](./tasks/task_4.md)
    - [Task Five — Model-based evaluation](./tasks/task_5.md)
- [Deliverables](#deliverables)
- [Useful Resources](#useful-resources)
- [Contributing](#contributing)

## **Introduction**

Generative AI applications have become a part of everyday life. Smart agents, RAG applications, chatbots, and many more are used in virtually every aspect of life. With the capabilities of Generative AI, these apps are now more capable than ever before. Unfortunately, LLMs make mistakes for several reasons—limitations in training data, model constraints, misinterpretation of context, and other factors. These errors manifest as model hallucinations, inconsistent or contradictory answers, irrelevant context, or generic responses.

LLM evaluation comes to the rescue, ensuring we build trustworthy Gen AI apps. Without continuously assessing these applications, you risk your users receiving irrelevant, inaccurate, or hallucinated results. Fortunately, there are tools available to help identify and mitigate these issues.

In this project, you’ll work on a chatbot for a smartphone sales website, but the main focus is on evaluating its performance. You'll use tools like Langfuse to collect traces, metrics, and scores, and Ragas to run different model-based assessments. This helps ensure the quality and reliability of the chatbot, especially in how it provides recommendations and comparisons. The metrics we gather will help us improve our app to serve our customers better.

The full code for the application (built with LangChain) is provided for you. Here is a breakdown of the application’s components:

1. Interface — for now, it is a console-based application. Users type their queries about smartphones and receive a response.
2. Knowledge bases —it integrates with a Qdrant vector store containing specifications for various smartphones. You could also use a relational database here.
3. Retriever component — uses embeddings to index product data for semantic search for the most relevant smartphone model based on the user’s query.
4. Generative component — generates responses that incorporate retrieved smartphone specifications. We combine user queries and retrieved data to produce contextually relevant answers.

This is part one of a series on building production-ready LLM apps. Here, your overall goal is to add monitoring and run various evaluations on this application to ensure it performs as expected. Logs allow you to monitor usage costs, latency, inputs, outputs, and other aspects of the app. You can then use this information to enhance your application over time.

## **Setup**

This project uses [uv](https://docs.astral.sh/uv/) for Python package management. Follow these steps to get started:

### Prerequisites

1. Install uv:
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Verify installation:
   ```bash
   uv --version
   ```

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd LLM-evals
   ```

2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

   This will:
   - Create a virtual environment in `.venv/`
   - Install all dependencies from `pyproject.toml`
   - Generate/update the `uv.lock` file for reproducible builds

3. Set up environment variables:
   ```bash
   cp .env.sample .env
   # Edit .env with your API keys and configuration
   ```

### Running the Application

```bash
uv run python main.py
```

If your IDE (VS Code, PyCharm) isn't recognizing the environment or you need to use tools that aren't uv-aware, activate the virtual environment manually:
```bash
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Run the application
python main.py
```

### Adding New Dependencies

To add new packages to the project:

```bash
uv add <package-name>
```

For development dependencies:

```bash
uv add --dev <package-name>
```
## **Learning Outcomes**

By the end of this project, you'll build a complete evaluation pipeline for an LLM application. You'll gain hands-on experience with evaluation techniques such as analytics, human-as-a-judge, and LLM-as-a-judge. You’ll use tools like Langfuse and Ragas to supercharge LLM evaluation. This project will help you ensure that your LLM-powered app offers accurate recommendations and consistently meets high-performance and reliability standards.

## **Project Structure**

Here are the main directories and files in this repo:

```markdown
  ├── assets/
  │   └── images/
  ├── datasets/
  │   └── smartphones.json
  ├── src/
  │   └── llm_evals/
  ├── tasks/
  │   ├── task_1.md
  │   ├── task_2.md
  │   ├── task_3.md
  │   ├── task_4.md
  │   └── task_5.md
  ├── .env.sample
  ├── .gitignore
  ├── main.py
  ├── pyproject.toml
  ├── README.md
  └── uv.lock
```

## **Tasks**

The project is divided into various tasks that you need to complete. The tasks are located in the [tasks](./tasks) folder of the repository. Each task includes all the necessary objectives, suggested development steps, deliverables, and useful resources. Here's a brief overview of each task:

- **Task One — Introduction and Setup:** Set up Langfuse, Qdrant vector store, and API keys for the project.
- **Task Two — Monitoring:** Collect logs and metrics via Langfuse to understand how the application is performing.
- **Task Three — User feedback**: Collect user feedback to understand how your application is performing.
- **Task Four  — Annotation**: Use the Langfuse UI to annotate traces. Useful for expert evaluation of your LLM application.
- **Task Five — Model-based evaluation**: Use Ragas to run model-based evaluation.

## **Useful Resources**

Each task contains a collection of resources that will be helpful for you as you solve the task. There are links to topics in Hyperskill, documentation, and other helpful tutorials that you can use. You may not always need to use all the provided resources if you're already familiar with the concepts. In addition to the provided resources, you can always discuss with others and experts. You can use various channels — GitHub Issues, GitHub Discussions, PRs, or Discord.

## Deliverables

Each task contains a set of deliverables that bring you close to achieving the final goal. The final product is a fully-monitored LLM application. You should see traces and evaluation results in Langfuse.

## **The Flow**

Fork → Clone → Branch → Implement → PR → Review

- Fork this repo to your own GitHub account.
- Create a new branch for each task (ensure to use descriptive names) if applicable (if there is any code that has to be implemented).
- Implement the solution based on the task descriptions.
- Push the branch to the forked repo.
- Create a Pull Request from the fork back to the main repo.
- We will review the PR and provide feedback through GitHub.