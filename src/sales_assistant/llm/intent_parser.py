from __future__ import annotations


class IntentParser:
    def parse(self, question: str) -> dict[str, str]:
        return {"question": question}
