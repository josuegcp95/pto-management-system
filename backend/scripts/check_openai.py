"""Verify the OpenAI API key works and can make a real request.

Run from backend/:  python -m scripts.check_openai
"""

from openai import OpenAI
from app.config import get_settings

# Cheapest current model; this test costs a tiny fraction of a cent.
TEST_MODEL = "gpt-5.4-nano"

def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is not set in backend/.env")

    client = OpenAI(api_key=settings.openai_api_key)

    # 1. Free check: can the key list models?
    model_ids = {m.id for m in client.models.list()}
    print(f"Key works. {len(model_ids)} models available.")

    if TEST_MODEL not in model_ids:
        raise SystemExit(f"{TEST_MODEL} is not available to this project.")

    # 2. Real request: a tiny prompt to confirm generation works.
    response = client.responses.create(
        model=TEST_MODEL,
        input="Reply with exactly: PTO API connection OK",
    )
    print(f"{TEST_MODEL} replied: {response.output_text}")


if __name__ == "__main__":
    main()