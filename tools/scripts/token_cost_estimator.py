#!/usr/bin/env python3
"""
Token Cost Estimator CLI

Estimate and compare AI API costs across different providers and models.
Supports Anthropic, OpenAI, Azure OpenAI, and Google Vertex AI pricing.

Usage:
    python token_cost_estimator.py --model claude-sonnet-4-5 --tokens 100000
    python token_cost_estimator.py --compare gpt-4o claude-sonnet-4-5 --tokens 100000
    python token_cost_estimator.py --monthly-budget 5000 --model claude-haiku-4-5
"""

import argparse
import json
from typing import Dict, Optional

# Pricing as of 2025 (per 1K tokens)
PRICING = {
    # Anthropic Claude models
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    
    # OpenAI GPT models
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    
    # Azure OpenAI (same as OpenAI base)
    "azure-gpt-4o": {"input": 0.0025, "output": 0.01},
    "azure-gpt-4-turbo": {"input": 0.01, "output": 0.03},
    
    # Google Vertex AI
    "gemini-pro": {"input": 0.00025, "output": 0.0005},
    "gemini-ultra": {"input": 0.0025, "output": 0.0075},
}

# Context window sizes (tokens)
CONTEXT_WINDOWS = {
    "claude-sonnet-4-5": 200000,
    "claude-opus-4": 200000,
    "claude-haiku-4-5": 200000,
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "gemini-pro": 1000000,
    "gemini-ultra": 1000000,
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Dict:
    """Calculate cost for a given model and token count."""
    if model not in PRICING:
        raise ValueError(f"Unknown model: {model}. Available: {list(PRICING.keys())}")
    
    prices = PRICING[model]
    input_cost = (input_tokens / 1000) * prices["input"]
    output_cost = (output_tokens / 1000) * prices["output"]
    total_cost = input_cost + output_cost
    
    context_window = CONTEXT_WINDOWS.get(model, "Unknown")
    
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "context_window": context_window,
    }


def format_currency(amount: float) -> str:
    """Format amount as USD."""
    return f"${amount:,.4f}"


def print_single_estimate(result: Dict):
    """Print cost estimate for a single model."""
    print("\n" + "=" * 60)
    print(f"COST ESTIMATE: {result['model']}")
    print("=" * 60)
    print(f"Input tokens:  {result['input_tokens']:,}")
    print(f"Output tokens: {result['output_tokens']:,}")
    print(f"Total tokens:  {result['total_tokens']:,}")
    print(f"Context window: {result['context_window']:,} tokens")
    print("-" * 60)
    print(f"Input cost:  {format_currency(result['input_cost'])}")
    print(f"Output cost: {format_currency(result['output_cost'])}")
    print(f"Total cost:  {format_currency(result['total_cost'])}")
    print("=" * 60 + "\n")


def print_comparison(results: list):
    """Print side-by-side comparison of multiple models."""
    print("\n" + "=" * 80)
    print("COST COMPARISON")
    print("=" * 80)
    
    # Header
    print(f"{'Model':<25} {'Input':<12} {'Output':<12} {'Total':<12} {'Savings':<10}")
    print("-" * 80)
    
    # Find cheapest for savings calculation
    min_cost = min(r['total_cost'] for r in results)
    
    for result in sorted(results, key=lambda x: x['total_cost']):
        savings = ((result['total_cost'] - min_cost) / result['total_cost'] * 100) if result['total_cost'] > 0 else 0
        savings_str = f"-{savings:.1f}%" if savings > 0 else "Best"
        
        print(f"{result['model']:<25} "
              f"{format_currency(result['input_cost']):<12} "
              f"{format_currency(result['output_cost']):<12} "
              f"{format_currency(result['total_cost']):<12} "
              f"{savings_str:<10}")
    
    print("=" * 80 + "\n")


def calculate_monthly_budget(model: str, monthly_budget: float) -> Dict:
    """Calculate how many tokens you can afford with a monthly budget."""
    if model not in PRICING:
        raise ValueError(f"Unknown model: {model}")
    
    prices = PRICING[model]
    avg_price = (prices["input"] + prices["output"]) / 2  # Assume 1:1 ratio
    
    max_tokens = (monthly_budget / avg_price) * 1000
    
    return {
        "model": model,
        "monthly_budget": monthly_budget,
        "max_tokens": int(max_tokens),
        "estimated_daily_tokens": int(max_tokens / 30),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Estimate AI API costs across different providers and models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --model claude-sonnet-4-5 --tokens 100000
  %(prog)s --compare gpt-4o claude-sonnet-4-5 --tokens 100000
  %(prog)s --monthly-budget 5000 --model claude-haiku-4-5
  %(prog)s --list-models
        """
    )
    
    parser.add_argument("--model", "-m", help="Model name to estimate")
    parser.add_argument("--tokens", "-t", type=int, help="Total token count")
    parser.add_argument("--input-tokens", type=int, help="Input tokens (default: 80%% of total)")
    parser.add_argument("--output-tokens", type=int, help="Output tokens (default: 20%% of total)")
    parser.add_argument("--compare", "-c", nargs="+", help="Compare multiple models")
    parser.add_argument("--monthly-budget", "-b", type=float, help="Monthly budget in USD")
    parser.add_argument("--list-models", action="store_true", help="List all available models")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    # List available models
    if args.list_models:
        print("\nAvailable models:")
        print("-" * 60)
        for model, prices in PRICING.items():
            context = CONTEXT_WINDOWS.get(model, "Unknown")
            context_str = f"{context:,}" if isinstance(context, int) else str(context)
            print(f"{model:<25} Input: ${prices['input']:.4f}/1K  Output: ${prices['output']:.4f}/1K  (Context: {context_str})")
        print()
        return
    
    # Monthly budget calculation
    if args.monthly_budget and args.model:
        result = calculate_monthly_budget(args.model, args.monthly_budget)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "=" * 60)
            print(f"BUDGET PLANNING: {result['model']}")
            print("=" * 60)
            print(f"Monthly budget:     {format_currency(result['monthly_budget'])}")
            print(f"Max tokens/month:   {result['max_tokens']:,}")
            print(f"Max tokens/day:     {result['estimated_daily_tokens']:,}")
            print("=" * 60 + "\n")
        return
    
    # Single model or comparison
    if args.compare:
        models = args.compare
    elif args.model:
        models = [args.model]
    else:
        parser.error("Must specify either --model or --compare")
    
    # Calculate token distribution
    if args.input_tokens and args.output_tokens:
        input_tokens = args.input_tokens
        output_tokens = args.output_tokens
    elif args.tokens:
        input_tokens = int(args.tokens * 0.8)
        output_tokens = int(args.tokens * 0.2)
    else:
        parser.error("Must specify either --tokens or both --input-tokens and --output-tokens")
    
    # Calculate costs
    results = []
    for model in models:
        try:
            result = calculate_cost(model, input_tokens, output_tokens)
            results.append(result)
        except ValueError as e:
            print(f"Error: {e}")
            return
    
    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    elif len(results) == 1:
        print_single_estimate(results[0])
    else:
        print_comparison(results)


if __name__ == "__main__":
    main()
