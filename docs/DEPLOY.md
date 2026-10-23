# Deploy: PitCrew on Bedrock AgentCore Runtime (teammate, ~15 min)

Goal: the crew runs as a managed agent on **Amazon Bedrock AgentCore Runtime**, and we can invoke the
Sourcing agent there during the demo. Do this in the workshop's browser VS Code (credentials already set).
Mudit is enabling the model in parallel (`docs/BEDROCK.md`); you need the model ID from him.

## 1. Get the code (2 min)

```bash
cd /workshop
git clone https://github.com/MuditUpadhyay04/AI-Agentic-Hack.git && cd AI-Agentic-Hack
pip3 install -r requirements-agent.txt     # agent only: shiny fails to build on the workshop ARM box
python3 scripts/run_sourcing.py            # offline sanity check: ends with PO-7711 ... Vendor C, $492
```

## 2. Deploy to AgentCore (8–10 min)

If the workshop kit has its own deploy script, use it with **`agentcore/agent.py` as the entrypoint**.
Otherwise, the AgentCore starter toolkit:

**Pre-flight (2 min, do this first):** run the exact entrypoint the container runs, against Bedrock:

```bash
export AWS_REGION=us-east-1 PITCREW_LLM=bedrock PITCREW_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
python3 -m agentcore.agent &          # starts on port 8080
sleep 8; curl -s localhost:8080/ping
curl -s -X POST localhost:8080/invocations -H 'Content-Type: application/json' -d '{"action":"sourcing"}' | head -c 600
kill %1
```

You want `"mode": "bedrock"` and `PO-7711` in the output. If it says `offline (fallback)`, fix Bedrock first
(docs/BEDROCK.md) — deploying won't fix it.

```bash
pip3 install bedrock-agentcore-starter-toolkit
agentcore configure --entrypoint agentcore/agent.py --name pitcrew \
  --requirements-file requirements-agent.txt --region "$AWS_REGION" \
  --deployment-type container --disable-memory --non-interactive
#   container: the dependencies (scipy, pandas, pvlib...) are too big for the 250 MB zip deploy
#   --disable-memory: we don't use AgentCore Memory, and creating it adds minutes
agentcore launch \
  --env PITCREW_LLM=bedrock \
  --env PITCREW_MODEL_ID=<model ID from Mudit, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0>
```

`launch` builds the container in CodeBuild and prints the **agent runtime ARN**. Copy it.

If `--env` isn't accepted by your toolkit version, run `agentcore launch` without it: `agent.py` defaults
to `PITCREW_LLM=bedrock` and the code's default model ID; then make sure Mudit enables that model.

If `configure`/`launch` fails creating an IAM role (workshop accounts sometimes block `iam:CreateRole`),
use the workshop kit's `setup_agentcore_role.py` and pass its role ARN with `--execution-role <arn>`.

The execution role needs Bedrock invoke permission (`bedrock:InvokeModel`,
`bedrock:InvokeModelWithResponseStream`); the toolkit's auto-created role has it. If invoke returns
AccessDenied on the model, add those two actions to the role in IAM.

## 3. Invoke it (2 min)

```bash
agentcore invoke '{"action": "sourcing"}'
# or, from anywhere with credentials:
python3 scripts/invoke_agentcore.py --arn <runtime ARN> --action sourcing
```

Success = `[Sourcing] ...` turns in the model's words, ending with PO-7711 to Vendor C ($492).
Other actions on the same runtime: `predict` (Matthew's failure model, `{"action": "predict", "udi": 162}`), `plan_mill`, `approve`, `grow`.

## 4. For the demo (1 min)

- Keep a terminal open with the `agentcore invoke` command ready, to show the same agent running on
  AgentCore.
- **CloudWatch** → *GenAI Observability* / *Bedrock AgentCore* → the runtime → open the latest trace to
  show the model's tool calls (the "proof" slide).
- The console itself (`shiny run app/app.py --port 8000 --host 0.0.0.0`) can run in the workshop VS Code
  with `PITCREW_LLM=bedrock`; open port 8000 from the Ports tab.

## 5. Cleanup after judging

```bash
agentcore destroy          # or the kit's cleanup steps; runtimes and ECR images can cost money
```
