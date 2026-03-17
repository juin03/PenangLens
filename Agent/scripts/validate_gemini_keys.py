import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import List, Tuple

import requests
from dotenv import load_dotenv


DEFAULT_MODEL = "gemini-2.5-flash"
GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass
class KeyCheckResult:
    key: str
    ok: bool
    status_code: int
    reason: str


def mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:8]}...{key[-4:]}"


def parse_keys(raw: str) -> List[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


def probe_key(key: str, model: str, timeout_s: float) -> KeyCheckResult:
    url = GENERATE_URL.format(model=model)
    params = {"key": key}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Reply with exactly: OK"}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 4,
            "temperature": 0,
        },
    }

    try:
        response = requests.post(url, params=params, json=payload, timeout=timeout_s)
    except requests.RequestException as exc:
        return KeyCheckResult(key=key, ok=False, status_code=0, reason=f"network_error: {exc}")

    if response.ok:
        return KeyCheckResult(key=key, ok=True, status_code=response.status_code, reason="ok")

    reason = f"http_{response.status_code}"
    try:
        body = response.json()
        msg = body.get("error", {}).get("message")
        if msg:
            reason = f"{reason}: {msg}"
    except json.JSONDecodeError:
        text = (response.text or "").strip()
        if text:
            reason = f"{reason}: {text[:200]}"

    return KeyCheckResult(key=key, ok=False, status_code=response.status_code, reason=reason)


def summarize(results: List[KeyCheckResult]) -> Tuple[List[str], List[KeyCheckResult]]:
    valid = [r.key for r in results if r.ok]
    invalid = [r for r in results if not r.ok]
    return valid, invalid


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a list of Gemini API keys and print a filtered key list. "
            "Only masked keys are printed."
        )
    )
    parser.add_argument(
        "--keys",
        default="",
        help=(
            "Comma-separated API keys. "
            "If omitted, reads GOOGLE_GENERATIVE_AI_API_KEY, GOOGLE_API_KEYS, then GOOGLE_API_KEY from .env/env."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between key probes in seconds")
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional path to write only valid keys as comma-separated text.",
    )

    args = parser.parse_args()

    load_dotenv()

    raw_keys = args.keys.strip()
    if not raw_keys:
        raw_keys = (
            os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "").strip()
            or os.getenv("GOOGLE_API_KEYS", "").strip()
            or os.getenv("GOOGLE_API_KEY", "").strip()
        )

    if not raw_keys:
        print("No keys found. Provide --keys or set GOOGLE_GENERATIVE_AI_API_KEY/GOOGLE_API_KEYS/GOOGLE_API_KEY.")
        return 1

    keys = parse_keys(raw_keys)
    if not keys:
        print("No parsable keys found.")
        return 1

    print(f"Testing {len(keys)} key(s) against model '{args.model}'...")

    results: List[KeyCheckResult] = []
    for idx, key in enumerate(keys, start=1):
        result = probe_key(key=key, model=args.model, timeout_s=args.timeout)
        results.append(result)
        status = "VALID" if result.ok else "INVALID"
        print(f"[{idx:02d}/{len(keys):02d}] {mask_key(key)} -> {status} ({result.reason})")
        time.sleep(max(args.sleep, 0.0))

    valid_keys, invalid_items = summarize(results)

    print("\nSummary")
    print(f"- Valid keys  : {len(valid_keys)}")
    print(f"- Invalid keys: {len(invalid_items)}")

    if valid_keys:
        masked_valid = ", ".join(mask_key(k) for k in valid_keys)
        print(f"- Valid key masks: {masked_valid}")
        print("\nUse this in .env:")
        print(f"GOOGLE_GENERATIVE_AI_API_KEY={','.join(valid_keys)}")
    else:
        print("No valid keys available.")

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(",".join(valid_keys))
        print(f"\nWrote valid keys to: {args.output_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
