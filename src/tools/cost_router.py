"""
Model Cost Router & Token Allocation Optimizer for MCP Autonomous Agents
Evaluates prompt complexity, token budget ceilings, and reasoning depth requirements
to dispatch queries between Ultra-Fast Edge models (DeepSeek V4.1-Flash) and Frontier engines (Claude 5 Fable / GPT-6 Astra).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
try:
    from ..protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult
except (ImportError, ValueError):
    from protocol import ToolDefinition, ToolParameterSchema, ToolExecutionResult


@dataclass(frozen=True)
class ModelTierSpec:
    """Pricing and performance characteristics for modern 2026 model endpoints."""
    model_id: str
    tier_category: str
    cost_per_million_input: float
    cost_per_million_output: float
    max_context_window: int
    median_latency_ms: float
    best_for: str


# 2026 Active Frontier Model Matrix
KNOWN_MODELS: Dict[str, ModelTierSpec] = {
    "deepseek-v4.1-flash": ModelTierSpec(
        model_id="deepseek-v4.1-flash",
        tier_category="edge_arbitration",
        cost_per_million_input=0.20,
        cost_per_million_output=0.40,
        max_context_window=128000,
        median_latency_ms=14.5,
        best_for="Unit testing, fast JSON parsing, code linting, simple function calls"
    ),
    "claude-5-fable": ModelTierSpec(
        model_id="claude-5-fable",
        tier_category="frontier_reasoning",
        cost_per_million_input=12.00,
        cost_per_million_output=36.00,
        max_context_window=500000,
        median_latency_ms=115.0,
        best_for="Deep multi-file architecture refactoring, complex mathematical proofs, AST security analysis"
    ),
    "gpt-6-astra": ModelTierSpec(
        model_id="gpt-6-astra",
        tier_category="frontier_reasoning",
        cost_per_million_input=10.00,
        cost_per_million_output=30.00,
        max_context_window=256000,
        median_latency_ms=95.0,
        best_for="High-order reasoning, algorithmic design, dynamic agent synthesis"
    ),
    "gemini-3.8-flash": ModelTierSpec(
        model_id="gemini-3.8-flash",
        tier_category="edge_arbitration",
        cost_per_million_input=0.15,
        cost_per_million_output=0.30,
        max_context_window=1000000,
        median_latency_ms=12.0,
        best_for="Massive document scanning, log ingestion, high-speed telemetry ingestion"
    )
}


class TokenRouterPolicyEngine:
    """Calculates optimal model routing based on prompt entropy and task requirements."""

    FRONTIER_TRIGGER_KEYWORDS: List[str] = [
        "refactor", "security audit", "deadlock", "race condition", "formal verification",
        "cryptographic", "concurrency", "distributed consensus", "raft", "paxos", "zero-copy"
    ]

    @classmethod
    def evaluate_task(cls, prompt_text: str, estimated_input_tokens: int, max_budget_usd: float = 1.0) -> Dict[str, Any]:
        normalized = prompt_text.lower()
        trigger_matches = [kw for kw in cls.FRONTIER_TRIGGER_KEYWORDS if kw in normalized]

        requires_frontier = len(trigger_matches) > 0 or estimated_input_tokens > 64000
        chosen_id = "claude-5-fable" if requires_frontier else "deepseek-v4.1-flash"
        chosen_spec = KNOWN_MODELS[chosen_id]

        # Calculate estimated pricing
        est_output_tokens = min(2000, max(250, int(estimated_input_tokens * 0.35)))
        cost_chosen = (estimated_input_tokens / 1_000_000 * chosen_spec.cost_per_million_input) + \
                      (est_output_tokens / 1_000_000 * chosen_spec.cost_per_million_output)

        # Baseline comparison against always using Claude 5 Fable
        baseline_frontier = KNOWN_MODELS["claude-5-fable"]
        cost_baseline = (estimated_input_tokens / 1_000_000 * baseline_frontier.cost_per_million_input) + \
                        (est_output_tokens / 1_000_000 * baseline_frontier.cost_per_million_output)

        savings_usd = max(0.0, cost_baseline - cost_chosen)
        savings_pct = (savings_usd / cost_baseline * 100.0) if cost_baseline > 0 else 0.0

        return {
            "recommended_model": chosen_spec.model_id,
            "tier": chosen_spec.tier_category,
            "triggers_detected": trigger_matches,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": est_output_tokens,
            "estimated_cost_usd": round(cost_chosen, 6),
            "baseline_frontier_cost_usd": round(cost_baseline, 6),
            "estimated_savings_usd": round(savings_usd, 6),
            "savings_percentage": round(savings_pct, 1),
            "within_budget": cost_chosen <= max_budget_usd,
            "rationale": f"Selected {chosen_spec.model_id} for {chosen_spec.best_for}."
        }


def get_cost_router_tool_definition() -> ToolDefinition:
    """Exposes tool metadata to MCP protocol engine."""
    return ToolDefinition(
        name="calculate_model_route",
        description="Analyzes prompt complexity and task parameters to recommend optimal routing between Fast Edge (DeepSeek V4.1) and Frontier Reasoning (Claude 5 Fable/GPT-6), calculating exact token cost savings.",
        inputSchema=ToolParameterSchema(
            type="object",
            properties={
                "task_description": {
                    "type": "string",
                    "description": "Summary or code context of the task being executed."
                },
                "estimated_tokens": {
                    "type": "integer",
                    "description": "Approximate token count of input context (default: 3000)."
                },
                "max_budget_usd": {
                    "type": "number",
                    "description": "Hard budget limit per single call in USD (default: 0.50)."
                }
            },
            required=["task_description"]
        )
    )


def handle_router_invocation(arguments: Dict[str, Any]) -> ToolExecutionResult:
    """Entry point for executing the cost router tool from an MCP client request."""
    task_desc = arguments.get("task_description")
    if not task_desc or not isinstance(task_desc, str):
        return ToolExecutionResult.failure("Missing 'task_description' argument.")

    tokens = int(arguments.get("estimated_tokens", 3000))
    budget = float(arguments.get("max_budget_usd", 0.50))

    try:
        decision = TokenRouterPolicyEngine.evaluate_task(
            prompt_text=task_desc,
            estimated_input_tokens=tokens,
            max_budget_usd=budget
        )
        report = (
            f"[NexusMCP Route Decision: {decision['recommended_model']}]\n"
            f"Tier: {decision['tier'].upper()} | Within Budget: {decision['within_budget']}\n"
            f"Triggers: {decision['triggers_detected'] or 'None (Routine Fast Path)'}\n"
            f"Est. Cost: ${decision['estimated_cost_usd']:.6f} (vs Frontier: ${decision['baseline_frontier_cost_usd']:.6f})\n"
            f"Net Savings: ${decision['estimated_savings_usd']:.6f} (-{decision['savings_percentage']}%)\n"
            f"Rationale: {decision['rationale']}"
        )
        return ToolExecutionResult.success(report)
    except Exception as err:
        return ToolExecutionResult.failure(f"Router Arbitration Error: {err}")
