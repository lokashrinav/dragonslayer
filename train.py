"""Minecraft Speedrun — Gemma RL Post-Training Pipeline

Fine-tunes Gemma-3 on speedrun trajectories using GRPO (Group Relative Policy Optimization).
Reward signal comes from the HUD environment's objective completion + time bonuses.

Inference backends:
    - Local: load model weights directly (needs GPU)
    - Fireworks AI: use Fireworks API for inference ($30 hackathon credits)

Usage:
    python train.py --model google/gemma-3-4b-it --epochs 3
    python train.py --model google/gemma-3-4b-it --backend fireworks --collect-only
    python train.py --resume checkpoints/latest
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch.utils.data import Dataset


FIREWORKS_MODELS = {
    "google/gemma-3-4b-it": "accounts/fireworks/models/gemma3-4b-it",
    "google/gemma-3-12b-it": "accounts/fireworks/models/gemma3-12b-it",
    "google/gemma-3-27b-it": "accounts/fireworks/models/gemma3-27b-it",
}


def fireworks_generate(prompt: str, model: str, temperature: float = 0.7) -> str:
    """Generate text via Fireworks AI API."""
    import requests as req
    fw_model = FIREWORKS_MODELS.get(model, model)
    api_key = os.environ.get("FIREWORKS_API_KEY", "")
    r = req.post(
        "https://api.fireworks.ai/inference/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": fw_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": temperature,
        },
        timeout=30,
    )
    return r.json()["choices"][0]["message"]["content"]


@dataclass
class TrainConfig:
    model_name: str = "google/gemma-3-4b-it"
    backend: str = "local"  # "local" or "fireworks"
    learning_rate: float = 1e-5
    epochs: int = 3
    batch_size: int = 4
    max_seq_len: int = 4096
    grad_accum_steps: int = 4
    warmup_ratio: float = 0.1
    kl_coeff: float = 0.05
    gamma: float = 0.99
    clip_range: float = 0.2
    group_size: int = 8  # GRPO group size
    checkpoint_dir: str = "checkpoints"
    trajectory_dir: str = "trajectories"
    tasks: list = field(default_factory=lambda: ["speedrun_easy", "speedrun_medium"])
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32


class TrajectoryDataset(Dataset):
    """Dataset of (state, action, reward) trajectories from MC speedrun episodes."""

    def __init__(self, trajectory_dir: str, tokenizer):
        self.tokenizer = tokenizer
        self.episodes = []
        traj_path = Path(trajectory_dir)
        if traj_path.exists():
            for f in sorted(traj_path.glob("*.jsonl")):
                with open(f) as fh:
                    episode = [json.loads(line) for line in fh]
                    if episode:
                        self.episodes.append(episode)

    def __len__(self):
        return len(self.episodes)

    def __getitem__(self, idx):
        episode = self.episodes[idx]
        turns = []
        for step in episode:
            state = step.get("state", "")
            action = step.get("action", "")
            reward = step.get("reward", 0.0)
            turns.append({"role": "user", "content": state})
            turns.append({"role": "assistant", "content": action})

        text = self.tokenizer.apply_chat_template(turns, tokenize=False)
        tokens = self.tokenizer(text, truncation=True, max_length=4096, return_tensors="pt")
        total_reward = sum(s.get("reward", 0.0) for s in episode)
        return {**tokens, "reward": torch.tensor(total_reward)}


def collect_trajectories(config: TrainConfig, model=None, tokenizer=None, n_episodes: int = 16):
    """Run the model against the MC environment and collect trajectories.
    Supports local model or Fireworks API backend."""
    import requests

    BOT_API = "http://127.0.0.1:3001"
    traj_dir = Path(config.trajectory_dir)
    traj_dir.mkdir(exist_ok=True)

    for ep in range(n_episodes):
        requests.post(f"{BOT_API}/reset", timeout=10)
        time.sleep(2)

        trajectory = []
        for step in range(50):  # max 50 actions per episode
            state_r = requests.get(f"{BOT_API}/state", timeout=10)
            state = state_r.json()

            prompt = format_state_prompt(state)
            if config.backend == "fireworks":
                action_text = fireworks_generate(prompt, config.model_name)
            else:
                inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
                with torch.no_grad():
                    output = model.generate(**inputs, max_new_tokens=256, temperature=0.7, do_sample=True)
                action_text = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

            action, args = parse_action(action_text)
            if action == "DONE":
                break

            try:
                r = requests.post(f"{BOT_API}/action", json={"action": action, "args": args}, timeout=120)
                result = r.json()
                step_reward = len(result.get("state", {}).get("newly_completed", [])) * 0.1
            except Exception:
                step_reward = -0.01
                result = {"error": "timeout"}

            trajectory.append({
                "state": prompt,
                "action": action_text,
                "reward": step_reward,
                "step": step,
            })

        # Episode reward from environment
        final_state = requests.get(f"{BOT_API}/state", timeout=10).json()
        n_completed = len(final_state.get("objectives_completed", []))
        for t in trajectory:
            t["episode_reward"] = n_completed / 16.0

        ep_path = traj_dir / f"ep_{int(time.time())}_{ep:04d}.jsonl"
        with open(ep_path, "w") as f:
            for t in trajectory:
                f.write(json.dumps(t) + "\n")

        print(f"Episode {ep+1}/{n_episodes}: {n_completed} objectives, {len(trajectory)} steps")


def format_state_prompt(state: dict) -> str:
    """Format MC state into a prompt for the model."""
    pos = state.get("position", {})
    inv = state.get("inventory", [])
    inv_str = ", ".join(f"{i['count']}x {i['name']}" for i in inv) if inv else "empty"

    return (
        f"You are a Minecraft speedrun bot. Current state:\n"
        f"Position: ({pos.get('x',0):.0f}, {pos.get('y',0):.0f}, {pos.get('z',0):.0f})\n"
        f"HP: {state.get('health',20)}/20 | Dimension: {state.get('dimension','overworld')}\n"
        f"Inventory: {inv_str}\n"
        f"Objectives done: {state.get('objectives_completed', [])}\n"
        f"Nearby: {json.dumps(state.get('nearby_blocks', {}))}\n"
        f"Entities: {json.dumps(state.get('nearby_entities', []))}\n\n"
        f"Choose your next action. Format: ACTION(arg1, arg2)\n"
        f"Actions: look_around, mine(block,n), craft(item,n), smelt(item,fuel,n), "
        f"equip(item), goto(x,y,z), attack(entity), dig_to_y(y), "
        f"build_nether_portal, enter_portal, find_structure(name), DONE"
    )


def parse_action(text: str) -> tuple:
    """Parse model output into (action_name, args_list)."""
    text = text.strip().split("\n")[0]  # first line only
    if "DONE" in text.upper():
        return "DONE", []

    action_map = {
        "look_around": 0, "mine": 2, "craft": 2, "smelt": 3,
        "equip": 1, "goto": 3, "attack": 1, "dig_to_y": 1,
        "build_nether_portal": 0, "enter_portal": 0, "find_structure": 1,
        "get_obsidian": 1,
    }

    for action, n_args in action_map.items():
        if action in text.lower():
            # Extract args from parentheses
            try:
                if "(" in text:
                    args_str = text[text.index("(") + 1:text.rindex(")")]
                    args = [a.strip().strip("'\"") for a in args_str.split(",") if a.strip()]
                    # Try to convert numeric args
                    parsed = []
                    for a in args:
                        try:
                            parsed.append(int(a))
                        except ValueError:
                            try:
                                parsed.append(float(a))
                            except ValueError:
                                parsed.append(a)
                    return action, parsed
                return action, []
            except (ValueError, IndexError):
                return action, []

    return "look_around", []


def train_grpo(config: TrainConfig):
    """GRPO training loop — Group Relative Policy Optimization."""
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model

    print(f"Loading {config.model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    if config.use_lora:
        lora_config = LoraConfig(
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

    os.makedirs(config.checkpoint_dir, exist_ok=True)

    for epoch in range(config.epochs):
        print(f"\n=== Epoch {epoch+1}/{config.epochs} ===")

        # Collect trajectories with current policy
        print("Collecting trajectories...")
        collect_trajectories(config, model, tokenizer, n_episodes=config.group_size)

        # Train on collected trajectories
        dataset = TrajectoryDataset(config.trajectory_dir, tokenizer)
        if len(dataset) == 0:
            print("No trajectories collected, skipping epoch")
            continue

        model.train()
        total_loss = 0
        n_batches = 0

        for i in range(0, len(dataset), config.batch_size):
            batch_rewards = []
            batch_logprobs = []

            for j in range(i, min(i + config.batch_size, len(dataset))):
                item = dataset[j]
                input_ids = item["input_ids"].to(model.device)
                attention_mask = item["attention_mask"].to(model.device)
                reward = item["reward"]

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits[:, :-1, :]
                targets = input_ids[:, 1:]
                logprobs = torch.nn.functional.log_softmax(logits, dim=-1)
                token_logprobs = logprobs.gather(2, targets.unsqueeze(-1)).squeeze(-1)
                seq_logprob = token_logprobs.sum()

                batch_rewards.append(reward)
                batch_logprobs.append(seq_logprob)

            if not batch_rewards:
                continue

            # GRPO: normalize rewards within group
            rewards = torch.stack(batch_rewards)
            mean_r = rewards.mean()
            std_r = rewards.std() + 1e-8
            advantages = (rewards - mean_r) / std_r

            # Policy gradient loss
            logprobs = torch.stack(batch_logprobs)
            loss = -(logprobs * advantages.to(model.device)).mean()

            loss.backward()
            if (n_batches + 1) % config.grad_accum_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        print(f"Epoch {epoch+1} avg loss: {avg_loss:.4f}")

        # Save checkpoint
        ckpt_path = os.path.join(config.checkpoint_dir, f"epoch_{epoch+1}")
        model.save_pretrained(ckpt_path)
        tokenizer.save_pretrained(ckpt_path)
        print(f"Saved checkpoint: {ckpt_path}")

    print("\nTraining complete!")


def main():
    parser = argparse.ArgumentParser(description="Minecraft Speedrun — Gemma RL Post-Training")
    parser.add_argument("--model", default="google/gemma-3-4b-it", help="Base model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--group-size", type=int, default=8, help="GRPO group size")
    parser.add_argument("--tasks", nargs="+", default=["speedrun_easy", "speedrun_medium"])
    parser.add_argument("--resume", type=str, default=None, help="Resume from checkpoint")
    parser.add_argument("--collect-only", action="store_true", help="Only collect trajectories")
    parser.add_argument("--lora-r", type=int, default=16)
    args = parser.parse_args()

    config = TrainConfig(
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        group_size=args.group_size,
        tasks=args.tasks,
        lora_r=args.lora_r,
    )

    if args.collect_only:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        model = AutoModelForCausalLM.from_pretrained(config.model_name, torch_dtype=torch.bfloat16, device_map="auto")
        collect_trajectories(config, model, tokenizer)
    else:
        train_grpo(config)


if __name__ == "__main__":
    main()
