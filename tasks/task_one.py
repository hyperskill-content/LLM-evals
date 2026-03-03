import os
import dotenv
import langfuse

from langfuse.openai import OpenAI

dotenv.load_dotenv()


OPENAI_MODEL = os.getenv("OPENAI_MODEL")

openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

instruction = ("You are a cell phone salesperson and are familiar with the models from the well-known manufacturers on the market."
               "Answer only in one sentence. ")

messages = [{"role": "system", "content": instruction}]
max_turns = 3

print("Ask up to 3 questions. Type 'exit' to quit.\n")


for turn in range(1, max_turns + 1):
    prompt = input(f"> ({turn}/{max_turns}) User: ").strip()
    if not prompt:
        print("Please enter a question.\n")
        continue
    if prompt.lower() in {"exit", "quit"}:
        print("Bye!")
        break

    messages.append({"role": "user", "content": prompt})

    response = openai.chat.completions.create(
        name="cellphone-chat",
        model=OPENAI_MODEL,
        messages=messages,
        metadata={
            "chat": "cellphone-chat",
            "turn": turn,
            "max_turns": max_turns,
        },
    )

    assistant_text = response.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": assistant_text})

    print(f"System: {assistant_text}\n")

else:
    # Runs only if the loop did not break early
    print("Reached the maximum of 3 questions. Conversation ended.")





# prompt = input("> ")
#
# response = openai.chat.completions.create(
#   name="test-chat",
#   model=OPENAI_MODEL,
#   messages=[
#       {"role": "system", "content": instruction},
#       {"role": "user", "content": prompt}],
#   metadata={"chat": "test-chat"},
# )
#
# print(f"User:", prompt)
#
# print(f"System:", response.choices[0].message.content)


