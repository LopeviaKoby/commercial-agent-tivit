from __future__ import annotations

from typing import Any


class ResponseWriter:
    def write(self, result: dict[str, Any]) -> str:
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            content = getattr(last_message, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append(block["text"])
                    elif isinstance(block, str):
                        parts.append(block)
                if parts:
                    return "\n".join(parts).strip()

            content_blocks = getattr(last_message, "content_blocks", None)
            if isinstance(content_blocks, list):
                texts = [
                    block.get("text")
                    for block in content_blocks
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                ]
                if texts:
                    return "\n".join(texts).strip()

        output_text = result.get("output")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        return "No fue posible generar una respuesta en este momento."
