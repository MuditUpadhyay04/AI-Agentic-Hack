# Bedrock: make the crew run on a real model (Mudit, ~10 min)

Goal: the agents (Sourcing first) answer from a Bedrock model instead of the offline narration, so the demo
is genuinely agentic on AWS. The code is ready; you only need model access, credentials and two env vars.

## 1. Turn on a model (2 min, AWS console)

1. AWS console → **Amazon Bedrock** → region the workshop uses (top right; usually `us-east-1` or
   `us-west-2`).
2. Left menu → **Model access** → make sure an **Anthropic Claude** model shows *Access granted*. If not,
   *Modify model access* → tick it → submit (usually instant in workshop accounts).
3. Note the **inference profile ID** (left menu → *Cross-region inference*), e.g.
   `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (the code's default). If the workshop kit has `infer.py`,
   run it: whatever model ID it uses successfully is the one to use.

## 2. Credentials in your terminal (2 min)

Workshop Studio → *Get AWS CLI credentials* → copy the block for your shell. PowerShell:

```powershell
$env:AWS_ACCESS_KEY_ID="..."; $env:AWS_SECRET_ACCESS_KEY="..."; $env:AWS_SESSION_TOKEN="..."
$env:AWS_REGION="us-east-1"        # the region from step 1
aws sts get-caller-identity        # should print the workshop account
```

(Or do all of this in the workshop's browser VS Code, where credentials are already set.)

## 3. Run the Sourcing agent on Bedrock (2 min)

```powershell
cd pitcrew
$env:PITCREW_LLM="bedrock"
$env:PITCREW_MODEL_ID="us.anthropic.claude-sonnet-4-5-20250929-v1:0"   # the ID from step 1
.\.venv\Scripts\python.exe scripts\run_sourcing.py
```

Success = first line says `mode: bedrock` and the Sourcing turn is written in the model's own words, with
tool calls under it. The PO must still be Vendor C, $492 (the numbers come from tools, not the model).

If it says `offline (fallback)`, the first turn shows the error:

| Error | Fix |
|---|---|
| `AccessDeniedException` / not authorized to invoke | Model access not granted (step 1) or wrong region |
| `ValidationException` ... model identifier is invalid | Use the inference profile ID (`us.` prefix) from step 1 |
| `UnrecognizedClientException` / expired token | Re-copy credentials (step 2) |
| `NoRegionError` | Set `$env:AWS_REGION` |

## 4. Show it in the console (1 min)

Same terminal (env vars still set):

```powershell
.\.venv\Scripts\shiny.exe run app\app.py --port 8000
```

Open http://localhost:8000 → **Parts & sourcing** → *Sourcing agent: work the queue*. The note under the
result says `crew mode: bedrock`. The other pages (mill, towers) use the same model through the same env vars.

## 5. What makes it "AWS agentic" (say this to the judges)

- **Amazon Bedrock** model drives each agent (Strands Agents SDK, `pitcrew/crew/strands_crew.py`).
- The model **chooses and calls tools** (`job_queue`, `fulfil_job`, `restock_local_hubs`,
  `plan_central_order`, `place_order`); every number comes from a tool, so it can't invent a price.
- **Guardrail by policy:** POs over $500 wait for a human; unverified vendors are refused by the tool.
- **Bedrock AgentCore Runtime** hosts the crew (see `docs/DEPLOY.md`), one isolated session per user.
- If the model or network fails mid-demo, that step falls back to the offline crew and says so on screen.
