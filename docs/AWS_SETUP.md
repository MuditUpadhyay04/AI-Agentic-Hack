# Morning setup in the workshop account (first 45 minutes)

From the track page (https://atx.rahman.dev/track-2.html): fresh/private browser window → Workshop Studio
(https://catalog.workshops.aws/join) → 12-digit event code → open the temporary AWS account → Event
dashboard → *Event outputs* → `VScodeIdeURL` (browser VS Code on `/workshop`).

## 1 · Get the code and check Bedrock (10 min)

```bash
cd /workshop
# upload pitcrew-v0.1.0.zip through the VS Code explorer (drag and drop), then:
unzip -q pitcrew-v0.1.0.zip && cd pitcrew
pip install -r requirements.txt
python -m pytest -q                       # 25 passed
curl -fsSL https://atx.rahman.dev/hackathon-kit.zip -o hackathon-kit.zip && unzip -qo hackathon-kit.zip
python infer.py                           # the kit's Bedrock smoke test: note which model id works
python scripts/fetch_data.py              # real AI4I file + DFW wind
```

## 2 · Run the console on Bedrock (10 min)

```bash
export PITCREW_LLM=bedrock
export PITCREW_MODEL_ID=<the id infer.py used>
export AWS_REGION=<workshop region>
shiny run app/app.py --port 8000 --host 0.0.0.0
```

Open the forwarded port from VS Code (Ports tab, or the code-server proxy path `/proxy/8000/`). If the model
call fails the console says so and continues offline — check `infer.py` first.

## 3 · Deploy the crew to AgentCore Runtime (20 min)

Follow the kit's README for `setup_agentcore_role.py` and its deploy step, using `agentcore/agent.py` as
the entrypoint instead of the kit's `agent.py`, with environment `PITCREW_LLM=bedrock` and
`PITCREW_MODEL_ID`. Then:

```bash
python scripts/invoke_agentcore.py --arn <runtime ARN> --action plan_tower --tower 7
```

Show the invocation trace in CloudWatch (AgentCore observability) during the "Proof" beat.

## 4 · Stretch (only if every core beat is green by 2:30)

- **A2A supplier**: `python agentcore/supplier_a2a.py --supplier "Lot-A Supplier" --port 9001` locally, or
  deploy with `--agentcore` as its own runtime (A2A protocol, port 9000; see the AgentCore A2A guide).
- **Gateway + Policy**: put `World` tools behind AgentCore Gateway and write the two Cedar rules from
  `pitcrew/ops.py` (`POLICY`) as AgentCore Policy, if the preview is enabled in the account.
- **Knowledge Base**: index `data/manuals/` in a Bedrock Knowledge Base and swap `search_manual` to it.

## Cleanup

AgentCore runtimes can incur charges: follow the kit's README cleanup steps when you finish.
