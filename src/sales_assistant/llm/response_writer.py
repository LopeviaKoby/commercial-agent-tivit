from __future__ import annotations


class ResponseWriter:
    def write(self, question: str, result: dict[str, object]) -> str:
        return f"Pending response generation for: {question}"
