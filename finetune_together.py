"""
OrchestrAI — Together AI Fine-Tuning Runner
============================================
Run this locally (NOT in the sandbox):

    pip install together
    python finetune_together.py

It will:
  1. Upload orchestrai_healing_train.jsonl to Together AI
  2. Start a LoRA fine-tuning job on llama-3.1-8b-instruct
  3. Poll until complete and print the model name
  4. Save the model name to .env so the app uses it automatically
"""

import os, time, sys
import together

API_KEY   = os.getenv("TOGETHER_API_KEY", "key_CesrRzVz59AFBrJnzGtYF")
TRAIN_FILE = os.path.join(os.path.dirname(__file__), "orchestrai_healing_train.jsonl")
BASE_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Reference"
JOB_NAME   = "orchestrai-healing-agent-v1"

client = together.Together(api_key=API_KEY)


def step(msg):
    print(f"\n{'─'*60}\n▶  {msg}\n{'─'*60}")


# ── 1. Upload dataset ─────────────────────────────────────────────────────────
step("Uploading training dataset...")
resp = client.files.upload(file=TRAIN_FILE, purpose="fine-tune")
file_id = resp.id
print(f"   File ID : {file_id}")
print(f"   Size    : {resp.size / 1024:.1f} KB")


# ── 2. Start fine-tuning job ──────────────────────────────────────────────────
step("Starting LoRA fine-tuning job...")
job = client.fine_tuning.create(
    training_file=file_id,
    model=BASE_MODEL,
    n_epochs=3,
    n_checkpoints=1,
    batch_size=4,
    learning_rate=2e-5,
    lora=True,
    lora_r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    lora_trainable_modules="all-linear",
    suffix=JOB_NAME,
    wandb_api_key=None,   # set if you have W&B
)
job_id = job.id
print(f"   Job ID  : {job_id}")
print(f"   Status  : {job.status}")
print(f"   Model   : {BASE_MODEL}")
print(f"\n   Track at: https://api.together.xyz/fine-tuning/{job_id}")


# ── 3. Poll until done ────────────────────────────────────────────────────────
step("Waiting for fine-tuning to complete (this takes ~30–60 min)...")
print("   Polling every 60 seconds. Ctrl+C to stop polling (job keeps running).\n")

TERMINAL = {"complete", "failed", "cancelled", "error"}
prev_status = None

try:
    while True:
        status_obj = client.fine_tuning.retrieve(job_id)
        status = status_obj.status

        if status != prev_status:
            ts = time.strftime("%H:%M:%S")
            print(f"   [{ts}] Status: {status}")
            prev_status = status

        if status in TERMINAL:
            break

        time.sleep(60)

except KeyboardInterrupt:
    print(f"\n   Interrupted. Job {job_id} is still running on Together AI.")
    print(f"   Re-run this script to resume polling, or check:")
    print(f"   https://api.together.xyz/fine-tuning/{job_id}")
    sys.exit(0)


# ── 4. Done ───────────────────────────────────────────────────────────────────
if status == "complete":
    model_name = status_obj.output_name
    step(f"Fine-tuning complete!")
    print(f"   Model name: {model_name}")

    # Persist to .env
    env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
    if os.path.exists(env_path):
        lines = open(env_path).readlines()
        lines = [l for l in lines if not l.startswith("TOGETHER_FINETUNED_MODEL=")]
        lines.append(f"TOGETHER_FINETUNED_MODEL={model_name}\n")
        open(env_path, "w").writelines(lines)
        print(f"   Saved to  : backend/.env  (TOGETHER_FINETUNED_MODEL)")
    else:
        print(f"\n   Add this to backend/.env:")
        print(f"   TOGETHER_FINETUNED_MODEL={model_name}")

    print(f"""
Next step — swap the model in orchestrator:
  In backend/agents/healing/orchestrator.py, change:

    groq_client = Groq(api_key=..., base_url="https://api.groq.com")
    model = "llama-3.3-70b-versatile"

  to:

    from together import Together
    together_client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
    model = "{model_name}"

  Or just run:  python swap_model_endpoint.py   (will be generated next)
""")
else:
    print(f"\n   Job ended with status: {status}")
    print(f"   Check logs at: https://api.together.xyz/fine-tuning/{job_id}")
