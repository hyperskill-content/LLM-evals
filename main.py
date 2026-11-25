import json
import os
import sys
import uuid

import dotenv
from langchain_community.docstore.document import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langfuse import get_client, observe, propagate_attributes
from langfuse.langchain import CallbackHandler
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

dotenv.load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "smartphones"

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

embeddings_model = OpenAIEmbeddings(
    model=os.getenv("OPENAI_EMBEDDINGS_MODEL"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    show_progress_bar=True,
)

conversation: list = []


@observe(name="embed-documents")
def embed_documents(json_path: str) -> QdrantVectorStore | None:
    """Load JSON data from smartphones.json and build or load a Qdrant vector store."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {json_path} was not found.")
        return None
    except json.JSONDecodeError as jde:
        print(f"Error decoding JSON from file {json_path}: {jde}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {json_path}: {e}")
        return None

    documents = []
    for entry in data:
        content = (
            f"Model: {entry.get('model', '')}\n"
            f"Price: {entry.get('price', '')}\n"
            f"Rating: {entry.get('rating', '')}\n"
            f"SIM: {entry.get('sim', '')}\n"
            f"Processor: {entry.get('processor', '')}\n"
            f"RAM: {entry.get('ram', '')}\n"
            f"Battery: {entry.get('battery', '')}\n"
            f"Display: {entry.get('display', '')}\n"
            f"Camera: {entry.get('camera', '')}\n"
            f"Card: {entry.get('card', '')}\n"
            f"OS: {entry.get('os', '')}\n"
            f"In Stock: {entry.get('in_stock', '')}"
        )
        documents.append(Document(page_content=content))

    try:
        qdrant_client = QdrantClient(url=QDRANT_URL)

        if not qdrant_client.collection_exists(collection_name=COLLECTION_NAME):
            vector_size = len(embeddings_model.embed_query("dimension check"))
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            qdrant_store = QdrantVectorStore(
                client=qdrant_client,
                collection_name=COLLECTION_NAME,
                embedding=embeddings_model,
            )
            if documents:
                qdrant_store.add_documents(documents=documents)
            return qdrant_store

        return QdrantVectorStore(
            client=qdrant_client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings_model,
        )
    except Exception as e:
        print(f"Error initializing the vector store: {e}")
        return None


product_db = embed_documents("datasets/smartphones.json")


@tool("SmartphoneInfo")
def smartphone_info_tool(model: str) -> str:
    """Retrieves information about a smartphone model from the product database."""
    if not isinstance(product_db, QdrantVectorStore):
        return "Product database is unavailable."
    try:
        results = product_db.similarity_search(model, k=1)
        if not results:
            return "Could not find information for the specified model."
        return results[0].page_content
    except Exception as e:
        return f"Error during smartphone information retrieval for model {model}: {e}"


@observe(name="generate-context")
def generate_context(ai_message: AIMessage) -> None:
    """Append the AI message and execute any requested tool calls."""
    conversation.append(ai_message)

    tool_calls = getattr(ai_message, "tool_calls", None) or []
    for tool_call in tool_calls:
        try:
            if tool_call.get("name") == "SmartphoneInfo":
                tool_output = smartphone_info_tool.invoke(tool_call)
                conversation.append(tool_output)
        except Exception as e:
            print(f"An error occurred while processing tool call {tool_call}: {e}")
            conversation.append(
                AIMessage(content=f"An error occurred while processing tool calls: {e}")
            )


def ask_yes_no(prompt: str) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("yes", "y"):
            return "Yes"
        if answer in ("no", "n"):
            return "No"
        print("Please answer Yes or No.")


def main() -> None:
    llm_with_tools = llm.bind_tools([smartphone_info_tool])

    langfuse = get_client()

    # Fetch production prompts managed in Langfuse
    context_langfuse_prompt = langfuse.get_prompt("context")
    review_langfuse_prompt = langfuse.get_prompt("review")
    goodbye_langfuse_prompt = langfuse.get_prompt("goodbye")

    context_prompt = ChatPromptTemplate.from_messages(
        [
            *context_langfuse_prompt.get_langchain_prompt(),
            MessagesPlaceholder(variable_name="conversation"),
        ]
    )

    review_prompt = ChatPromptTemplate.from_messages(
        [
            *review_langfuse_prompt.get_langchain_prompt(),
            MessagesPlaceholder(variable_name="conversation"),
        ]
    )

    goodbye_prompt = PromptTemplate.from_template(
        goodbye_langfuse_prompt.get_langchain_prompt()[0][1]
    )

    context_chain = context_prompt | llm_with_tools | generate_context
    review_chain = review_prompt | llm
    goodbye_chain = goodbye_prompt | llm

    users = ["James", "George", "Mike", "Sherlock"]
    user_id = users[uuid.uuid4().int % len(users)]
    session_id = f"session-{uuid.uuid4().hex[:8]}"

    langfuse_handler = CallbackHandler()

    try:
        print(
            "Welcome to the Smartphone Assistant! I can help you with smartphone features and comparisons."
        )
        while True:
            user_input = input("User: ").strip()
            if not user_input:
                continue

            with langfuse.start_as_current_observation(as_type="span", name="user-query") as span:
                span.update(input=user_input)

                with propagate_attributes(session_id=session_id, user_id=user_id):
                    if user_input.lower() in ["exit", "quit", "bye", "end"]:
                        goodbye_message = goodbye_chain.invoke(
                            {"user_id": user_id},
                            config={
                                "run_name": "goodbye-message",
                                "callbacks": [langfuse_handler],
                                "metadata": {"langfuse_prompt": goodbye_langfuse_prompt},
                            },
                        )
                        print(f"System: {goodbye_message.content}")
                        span.update(output=goodbye_message.content)

                        feedback = ask_yes_no("Was this conversation helpful? (Yes/No): ")
                        user_comment = input(
                            "Please give us a reason for your answer. This will help us improve: "
                        ).strip()
                        langfuse.create_score(
                            session_id=session_id,
                            name="conversation_usefulness",
                            value=feedback,
                            data_type="CATEGORICAL",
                            comment=user_comment or None,
                        )
                        return

                    conversation.append(HumanMessage(user_input))
                    context_chain.invoke(
                        {"user_input": user_input, "conversation": conversation},
                        config={
                            "run_name": "context",
                            "callbacks": [langfuse_handler],
                            "metadata": {"langfuse_prompt": context_langfuse_prompt},
                        },
                    )
                    response = review_chain.invoke(
                        {
                            "user_id": user_id,
                            "user_input": user_input,
                            "conversation": conversation,
                        },
                        config={
                            "run_name": "final-response",
                            "callbacks": [langfuse_handler],
                            "metadata": {"langfuse_prompt": review_langfuse_prompt},
                        },
                    )

                    print(f"System: {response.content}")
                    conversation.append(response)
                    span.update(output=response.content)

    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")
        sys.exit(1)
    finally:
        langfuse.flush()


if __name__ == "__main__":
    main()