"""Token estimates and context sizing (SPEC 1.3, Steps 2-3)."""

CHARS_PER_TOKEN = 3  # conservative: code and Markdown use more tokens per char than prose
ANSWER_RESERVE = 2048  # tokens kept free for the model's JSON answer
MIN_CONTEXT = 4096


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN + 1


def context_size(messages: list[dict], max_context: int) -> int:
    """num_ctx for this prompt: prompt + answer reserve, rounded up to a power of two, capped."""
    needed = sum(estimate_tokens(m["content"]) for m in messages) + ANSWER_RESERVE
    size = MIN_CONTEXT
    while size < needed:
        size *= 2
    return min(size, max_context)
