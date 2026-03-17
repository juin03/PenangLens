import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


CANDIDATE_API_VERSIONS = [
    "2024-10-21",
    "2024-06-01",
    "2024-02-15-preview",
]


@dataclass
class DeploymentInfo:
    name: str
    model: str


@dataclass
class ApiMode:
    name: str  # "classic" | "v1"
    api_version: str = ""


def _mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def _normalize_endpoint(endpoint: str) -> str:
    return endpoint.rstrip("/")


def _safe_json(resp: requests.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw": (resp.text or "").strip()[:500]}


def list_deployments(endpoint: str, api_key: str, api_version: str) -> tuple[list[DeploymentInfo], str]:
    url = f"{endpoint}/openai/deployments"
    params = {"api-version": api_version}
    headers = {"api-key": api_key}

    resp = requests.get(url, headers=headers, params=params, timeout=20)
    if not resp.ok:
        payload = _safe_json(resp)
        msg = payload.get("error", {}).get("message") or payload
        raise RuntimeError(f"List deployments failed ({resp.status_code}): {msg}")

    data = _safe_json(resp)
    rows = data.get("data", []) if isinstance(data, dict) else []

    deployments: list[DeploymentInfo] = []
    for row in rows:
        name = row.get("id") or row.get("name") or "(unknown)"
        model = row.get("model") or row.get("properties", {}).get("model", "(unknown)")
        deployments.append(DeploymentInfo(name=name, model=model))

    return deployments, api_version


def list_models_v1(endpoint: str, api_key: str) -> list[DeploymentInfo]:
    url = f"{endpoint}/openai/v1/models"
    headers = {"api-key": api_key}
    resp = requests.get(url, headers=headers, timeout=20)
    if not resp.ok:
        payload = _safe_json(resp)
        msg = payload.get("error", {}).get("message") or payload
        raise RuntimeError(f"List v1 models failed ({resp.status_code}): {msg}")

    data = _safe_json(resp)
    rows = data.get("data", []) if isinstance(data, dict) else []
    models: list[DeploymentInfo] = []
    for row in rows:
        mid = row.get("id") or row.get("name") or "(unknown)"
        models.append(DeploymentInfo(name=mid, model=mid))
    return models


def infer_task_type(model: str) -> str:
    low = (model or "").lower()
    if "embedding" in low:
        return "embeddings"
    return "chat"


def _is_probably_text_model(name: str) -> bool:
    low = (name or "").lower()
    prefixes = ("gpt", "o1", "o3", "o4", "codex", "model-router")
    return low.startswith(prefixes)


def smoke_test_deployment(endpoint: str, api_key: str, mode: ApiMode, dep: DeploymentInfo) -> tuple[bool, str]:
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    task_type = infer_task_type(dep.model)

    if mode.name == "v1":
        if task_type == "embeddings":
            url = f"{endpoint}/openai/v1/embeddings"
            payload = {
                "model": dep.name,
                "input": "hello from PenangLens",
            }
            params = None
        else:
            # Try responses first, then fallback to chat/completions
            resp_url = f"{endpoint}/openai/v1/responses"
            resp_payload = {
                "model": dep.name,
                "input": "Reply with exactly: OK",
                "max_output_tokens": 16,
            }
            resp = requests.post(resp_url, headers=headers, json=resp_payload, timeout=30)
            if resp.ok:
                body = _safe_json(resp)
                text = (body.get("output_text") or "").strip().replace("\n", " ")[:120]
                return True, f"responses ok (sample='{text}')"

            url = f"{endpoint}/openai/v1/chat/completions"
            payload = {
                "model": dep.name,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 8,
                "temperature": 0,
            }
            params = None
    else:
        if task_type == "embeddings":
            url = f"{endpoint}/openai/deployments/{dep.name}/embeddings"
            payload = {
                "input": "hello from PenangLens",
            }
        else:
            url = f"{endpoint}/openai/deployments/{dep.name}/chat/completions"
            payload = {
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 8,
                "temperature": 0,
            }
        params = {"api-version": mode.api_version}

    resp = requests.post(url, headers=headers, params=params, json=payload, timeout=30)

    if not resp.ok:
        body = _safe_json(resp)
        msg = body.get("error", {}).get("message") or body
        return False, f"{resp.status_code}: {msg}"

    body = _safe_json(resp)
    if task_type == "embeddings":
        vector_len = len((body.get("data") or [{}])[0].get("embedding", []))
        return True, f"embeddings ok (dim={vector_len})"

    content = ""
    try:
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        content = ""
    content = (content or "").strip().replace("\n", " ")[:120]
    return True, f"chat ok (sample='{content}')"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Azure OpenAI endpoint/key, list deployments, and smoke-test each deployment."
    )
    parser.add_argument("--endpoint", default="", help="Azure OpenAI endpoint, e.g. https://xxx.openai.azure.com")
    parser.add_argument("--api-key", default="", help="Azure OpenAI API key")
    parser.add_argument("--api-version", default="", help="Optional API version override")
    parser.add_argument("--test-all", action="store_true", help="Smoke-test all deployments (default true if no deployment specified)")
    parser.add_argument("--deployment", default="", help="Smoke-test only one deployment name")
    parser.add_argument("--model", default="", help="Smoke-test one explicit model/deployment name")
    parser.add_argument("--limit", type=int, default=8, help="When not using --test-all, number of likely text models to test")
    parser.add_argument("--show-all-models", action="store_true", help="Print full model list (can be very long)")
    args = parser.parse_args()

    load_dotenv()

    endpoint = (args.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
    api_key = (args.api_key or os.getenv("AZURE_OPENAI_API_KEY") or "").strip()

    if not endpoint or not api_key:
        print("Missing endpoint or API key. Provide --endpoint/--api-key or set AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_KEY.")
        return 1

    endpoint = _normalize_endpoint(endpoint)
    print(f"Endpoint: {endpoint}")
    print(f"API key : {_mask(api_key)}")

    api_versions = [args.api_version] if args.api_version else CANDIDATE_API_VERSIONS

    deployments: list[DeploymentInfo] = []
    mode: ApiMode | None = None
    last_error: Exception | None = None

    for version in api_versions:
        try:
            deployments, selected_version = list_deployments(endpoint, api_key, version)
            mode = ApiMode(name="classic", api_version=selected_version)
            break
        except Exception as exc:
            last_error = exc

    if mode is None:
        try:
            deployments = list_models_v1(endpoint, api_key)
            mode = ApiMode(name="v1")
        except Exception as exc:
            last_error = exc

    if mode is None:
        print(f"Could not list deployments/models with classic versions {api_versions} or v1 route.")
        print(f"Last error: {last_error}")
        return 2

    if mode.name == "classic":
        print(f"\nAPI mode used: classic (api-version={mode.api_version})")
    else:
        print("\nAPI mode used: v1")

    print(f"Deployments found: {len(deployments)}")

    if not deployments:
        print("No deployments found. Create a model deployment first in Azure AI Foundry/Portal.")
        return 3

    if args.show_all_models:
        for dep in deployments:
            print(f"- {dep.name}  (model={dep.model})")
    else:
        preview_count = min(len(deployments), 30)
        print(f"Showing first {preview_count} models (use --show-all-models for full list):")
        for dep in deployments[:preview_count]:
            print(f"- {dep.name}  (model={dep.model})")

    target_name = args.model or args.deployment
    if target_name:
        to_test = [d for d in deployments if d.name == target_name]
        if not to_test:
            to_test = [DeploymentInfo(name=target_name, model=target_name)]
    else:
        likely = [d for d in deployments if _is_probably_text_model(d.name)]
        to_test = deployments if args.test_all else likely[: max(args.limit, 1)]

    print("\nSmoke tests")
    ok_count = 0
    for dep in to_test:
        ok, msg = smoke_test_deployment(endpoint, api_key, mode, dep)
        status = "OK" if ok else "FAIL"
        print(f"- [{status}] {dep.name}: {msg}")
        if ok:
            ok_count += 1

    print(f"\nSummary: {ok_count}/{len(to_test)} deployments passed smoke test")

    print("\nHow to know what model you can use:")
    print("- Use the deployment NAME shown above in your API calls (not the raw model id).")
    print("- Deployment type tells the endpoint: chat/completions vs embeddings.")

    return 0 if ok_count > 0 else 5


if __name__ == "__main__":
    raise SystemExit(main())
