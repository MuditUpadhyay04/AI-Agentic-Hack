"""Call the deployed PitCrew runtime on Bedrock AgentCore.

    python scripts/invoke_agentcore.py --arn <runtime ARN> --action sourcing
    python scripts/invoke_agentcore.py --arn <runtime ARN> --action predict --udi 162

The starter kit's README has the exact deploy and invoke steps for the workshop account; this mirrors the
boto3 call (bedrock-agentcore client, invoke_agent_runtime). Session ids must be 33+ characters.
"""
from __future__ import annotations

import argparse
import json
import uuid

import boto3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arn", required=True)
    ap.add_argument("--action", default="plan_mill")
    ap.add_argument("--udi", type=int, default=162)
    ap.add_argument("--session", default=f"pitcrew-demo-{uuid.uuid4().hex}")
    ap.add_argument("--region", default=None)
    a = ap.parse_args()
    client = boto3.client("bedrock-agentcore", region_name=a.region)
    payload = {"action": a.action, "udi": a.udi}
    r = client.invoke_agent_runtime(agentRuntimeArn=a.arn, runtimeSessionId=a.session,
                                    payload=json.dumps(payload).encode())
    body = r["response"].read() if hasattr(r.get("response"), "read") else r.get("response")
    data = json.loads(body)
    if "risk" in data:
        print(f"Failure risk {data['risk']:.0%} -> {data['action']} (furthest from peers: {data['worst_signal']})")
    for t in data.get("turns", []):
        print(f"[{t['agent']}] {t['say']}")
    if data.get("recommendation"):
        print("\nRecommendation:", data["recommendation"].get("title"))


if __name__ == "__main__":
    main()
