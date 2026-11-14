import json

from llm import get_llm

with open("question.json", encoding="utf-8") as f:
    data = json.load(f)

answer = get_llm(data["question"])
print(answer)
