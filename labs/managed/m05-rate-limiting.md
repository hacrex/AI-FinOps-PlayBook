# M-05: Rate Limiting with Token Buckets

> Build a cost-aware rate limiter that prevents runaway API spend using token budgets and sliding windows.

---

## Objective

By the end of this lab, you will have:

- A token bucket rate limiter that tracks API spend in real-time
- Budget enforcement that blocks requests when limits are exceeded
- Alerting integration for budget threshold warnings
- A dashboard showing token consumption by team/project

**Time:** 60 minutes  
**Cost:** < $0.50 in API calls during testing

---

## Prerequisites

- Python 3.10+
- Redis installed (for distributed rate limiting)
- An API key for Anthropic, OpenAI, or Azure OpenAI
- Basic understanding of rate limiting concepts

```bash
# Install dependencies
pip install redis anthropic python-dotenv
```

---

## Background

Rate limiting in AI FinOps isn't just about protecting APIs from overload—it's about **cost containment**. Without limits, a single runaway process or misconfigured agent can burn through thousands of dollars in minutes.

### Key concepts

| Concept | Description |
|---------|-------------|
| **Token budget** | Maximum tokens allowed per time period (hour/day/month) |
| **Sliding window** | Rolling time window for rate calculation (more accurate than fixed windows) |
| **Burst allowance** | Temporary override for legitimate traffic spikes |
| **Soft vs hard limits** | Warnings at 80% vs hard blocks at 100% |

---

## Setup

### Step 1: Start Redis

```bash
docker run -d --name redis-rate-limiter -p 6379:6379 redis:7-alpine
```

Expected output:
```
redis-rate-limiter container started
```

### Step 2: Create environment file

Create `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
REDIS_HOST=localhost
REDIS_PORT=6379
DAILY_TOKEN_BUDGET=50000
HOURLY_TOKEN_BUDGET=10000
TEAM_ID=engineering-team-alpha
```

---

## Step-by-step

### Step 1: Build the token bucket rate limiter

Create `rate_limiter.py`:

```python
import redis
import time
from typing import Optional, Tuple
from datetime import datetime, timedelta

class TokenBudgetLimiter:
    def __init__(self, redis_host: str, redis_port: int, team_id: str):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.team_id = team_id
        
    def check_budget(self, requested_tokens: int, budget_type: str = 'daily') -> Tuple[bool, dict]:
        """
        Check if request fits within budget.
        Returns (allowed: bool, info: dict)
        """
        now = datetime.utcnow()
        
        if budget_type == 'daily':
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = 86400  # 24 hours
        elif budget_type == 'hourly':
            window_start = now.replace(minute=0, second=0, microsecond=0)
            ttl = 3600  # 1 hour
        else:
            raise ValueError(f"Unknown budget type: {budget_type}")
        
        window_key = f"budget:{self.team_id}:{budget_type}:{window_start.isoformat()}"
        
        # Get current usage
        current_usage = int(self.redis.get(window_key) or 0)
        
        # Load budget limit from env (in production, fetch from config service)
        import os
        budget_limit = int(os.getenv(f"{budget_type.upper()}_TOKEN_BUDGET", 100000))
        
        remaining = budget_limit - current_usage
        usage_percentage = (current_usage / budget_limit) * 100
        
        info = {
            'current_usage': current_usage,
            'budget_limit': budget_limit,
            'remaining': remaining,
            'usage_percentage': round(usage_percentage, 2),
            'window_resets_at': window_start + timedelta(seconds=ttl)
        }
        
        # Check soft limit (80%)
        if usage_percentage >= 80 and usage_percentage < 100:
            info['warning'] = f"Approaching {budget_type} budget limit ({usage_percentage:.1f}%)"
        
        # Check hard limit (100%)
        if current_usage + requested_tokens > budget_limit:
            info['blocked'] = True
            info['reason'] = f"Request would exceed {budget_type} budget"
            return False, info
        
        return True, info
    
    def record_usage(self, tokens_used: int, budget_type: str = 'daily'):
        """Record token usage in Redis"""
        now = datetime.utcnow()
        
        if budget_type == 'daily':
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = 86400
        elif budget_type == 'hourly':
            window_start = now.replace(minute=0, second=0, microsecond=0)
            ttl = 3600
        else:
            raise ValueError(f"Unknown budget type: {budget_type}")
        
        window_key = f"budget:{self.team_id}:{budget_type}:{window_start.isoformat()}"
        
        # Increment counter with TTL
        pipe = self.redis.pipeline()
        pipe.incrby(window_key, tokens_used)
        pipe.expire(window_key, ttl)
        pipe.execute()
    
    def get_usage_dashboard(self) -> dict:
        """Get current usage across all budget types"""
        now = datetime.utcnow()
        
        daily_window = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        hourly_window = now.replace(minute=0, second=0, microsecond=0).isoformat()
        
        daily_key = f"budget:{self.team_id}:daily:{daily_window}"
        hourly_key = f"budget:{self.team_id}:hourly:{hourly_window}"
        
        return {
            'team_id': self.team_id,
            'timestamp': now.isoformat(),
            'daily_usage': int(self.redis.get(daily_key) or 0),
            'hourly_usage': int(self.redis.get(hourly_key) or 0)
        }

# Example usage
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    limiter = TokenBudgetLimiter(
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        redis_port=int(os.getenv('REDIS_PORT', 6379)),
        team_id=os.getenv('TEAM_ID', 'default-team')
    )
    
    # Test budget check
    allowed, info = limiter.check_budget(requested_tokens=1000, budget_type='daily')
    print(f"Request allowed: {allowed}")
    print(f"Budget info: {info}")
```

### Step 2: Create the API proxy with rate limiting

Create `api_proxy.py`:

```python
import os
import anthropic
from dotenv import load_dotenv
from rate_limiter import TokenBudgetLimiter

load_dotenv()

# Initialize
limiter = TokenBudgetLimiter(
    redis_host=os.getenv('REDIS_HOST', 'localhost'),
    redis_port=int(os.getenv('REDIS_PORT', 6379)),
    team_id=os.getenv('TEAM_ID', 'default-team')
)

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def make_cost_aware_request(prompt: str, max_tokens: int = 1000) -> dict:
    """
    Make an API request with budget enforcement.
    """
    # Estimate input tokens (rough approximation: 1 token ≈ 4 chars)
    estimated_input_tokens = len(prompt) // 4
    total_estimated_tokens = estimated_input_tokens + max_tokens
    
    # Check budget before making request
    allowed, info = limiter.check_budget(total_estimated_tokens, 'daily')
    
    if not allowed:
        return {
            'success': False,
            'error': 'budget_exceeded',
            'message': info.get('reason', 'Daily token budget exceeded'),
            'budget_info': info
        }
    
    # Check for warning threshold
    if info.get('warning'):
        print(f"⚠️  BUDGET WARNING: {info['warning']}")
    
    try:
        # Make the actual API call
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Get actual token usage
        actual_tokens = response.usage.input_tokens + response.usage.output_tokens
        
        # Record usage
        limiter.record_usage(actual_tokens, 'daily')
        limiter.record_usage(actual_tokens, 'hourly')
        
        return {
            'success': True,
            'response': response.content[0].text,
            'tokens_used': actual_tokens,
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens,
            'budget_remaining': info['remaining'] - actual_tokens
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'api_error',
            'message': str(e)
        }

# Test the proxy
if __name__ == '__main__':
    test_prompt = "Explain quantum computing in 3 sentences."
    
    result = make_cost_aware_request(test_prompt, max_tokens=150)
    
    if result['success']:
        print(f"✅ Request successful")
        print(f"Response: {result['response'][:100]}...")
        print(f"Tokens used: {result['tokens_used']}")
        print(f"Budget remaining: {result['budget_remaining']}")
    else:
        print(f"❌ Request failed: {result['error']}")
        print(f"Message: {result['message']}")
        if 'budget_info' in result:
            print(f"Budget status: {result['budget_info']}")
```

### Step 3: Run multiple requests to test budget tracking

Create `test_rate_limiter.py`:

```python
from api_proxy import make_cost_aware_request
import time

print("Testing rate limiter with multiple requests...\n")

test_prompts = [
    "What is machine learning?",
    "Explain neural networks simply.",
    "What are transformers in AI?",
    "Describe reinforcement learning.",
    "What is the difference between supervised and unsupervised learning?"
]

for i, prompt in enumerate(test_prompts, 1):
    print(f"\n--- Request {i} ---")
    result = make_cost_aware_request(prompt, max_tokens=100)
    
    if result['success']:
        print(f"✅ Tokens used: {result['tokens_used']}")
        print(f"💰 Budget remaining: {result['budget_remaining']}")
    else:
        print(f"❌ Blocked: {result['message']}")
        break
    
    time.sleep(0.5)  # Avoid rate limiting at API level

# Show final dashboard
from rate_limiter import TokenBudgetLimiter
import os

limiter = TokenBudgetLimiter('localhost', 6379, os.getenv('TEAM_ID', 'default-team'))
dashboard = limiter.get_usage_dashboard()

print(f"\n{'='*50}")
print("USAGE DASHBOARD")
print(f"{'='*50}")
print(f"Team: {dashboard['team_id']}")
print(f"Daily usage: {dashboard['daily_usage']} tokens")
print(f"Hourly usage: {dashboard['hourly_usage']} tokens")
```

### Step 4: Test budget enforcement

Create `test_budget_limit.py` to simulate exceeding the budget:

```python
from rate_limiter import TokenBudgetLimiter
import os

limiter = TokenBudgetLimiter('localhost', 6379, os.getenv('TEAM_ID', 'default-team'))

# Manually set usage close to limit
print("Simulating near-budget scenario...")
limiter.record_usage(48000, 'daily')  # Assume 50k daily budget

# Try to make a large request
allowed, info = limiter.check_budget(5000, 'daily')

print(f"\nRequest for 5000 tokens:")
print(f"Allowed: {allowed}")
print(f"Current usage: {info['current_usage']}")
print(f"Budget limit: {info['budget_limit']}")
print(f"Remaining: {info['remaining']}")
print(f"Usage %: {info['usage_percentage']}%")

if info.get('warning'):
    print(f"\n⚠️  WARNING: {info['warning']}")

if info.get('blocked'):
    print(f"\n🚫 BLOCKED: {info['reason']}")
```

---

## Validate

### Expected outputs

**Step 3 output:**
```
Testing rate limiter with multiple requests...

--- Request 1 ---
✅ Tokens used: 87
💰 Budget remaining: 49913

--- Request 2 ---
✅ Tokens used: 92
💰 Budget remaining: 49821

...

==================================================
USAGE DASHBOARD
==================================================
Team: engineering-team-alpha
Daily usage: 456 tokens
Hourly usage: 456 tokens
```

**Step 4 output (budget exceeded):**
```
Simulating near-budget scenario...

Request for 5000 tokens:
Allowed: False
Current usage: 48000
Budget limit: 50000
Remaining: 2000
Usage %: 96.0%

⚠️  WARNING: Approaching daily budget limit (96.0%)

🚫 BLOCKED: Request would exceed daily budget
```

### Verification checklist

- [ ] Redis container is running
- [ ] First few requests succeed and track tokens
- [ ] Usage dashboard shows cumulative token count
- [ ] Requests are blocked when budget exceeded
- [ ] Warning messages appear at 80% threshold

---

## Cost Impact

**Without rate limiting:**
- Runaway process could consume unlimited tokens
- Example: Bug causes 10,000 requests/hour → $500-2000/hour in API costs

**With rate limiting:**
- Hard cap on hourly/daily spend
- Predictable cost ceiling
- Early warnings prevent surprises

**Estimated savings:** Prevents catastrophic cost incidents (potentially $10K+/month in avoided overruns)

---

## Advanced: Add Alerting

Create `alerting.py` for Slack/email notifications:

```python
import requests
import os
from rate_limiter import TokenBudgetLimiter

def send_slack_alert(message: str, webhook_url: str):
    """Send alert to Slack channel"""
    payload = {
        "text": f"🚨 AI Budget Alert\n{message}",
        "username": "FinOps Bot",
        "icon_emoji": ":warning:"
    }
    response = requests.post(webhook_url, json=payload)
    return response.status_code == 200

def monitor_budgets():
    """Check budgets and send alerts if thresholds exceeded"""
    limiter = TokenBudgetLimiter('localhost', 6379, os.getenv('TEAM_ID'))
    
    allowed, info = limiter.check_budget(0, 'daily')  # Just checking, not requesting
    
    slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
    
    if info['usage_percentage'] >= 100:
        msg = f"CRITICAL: Daily budget EXCEEDED\nTeam: {limiter.team_id}\nUsage: {info['usage_percentage']}%\nRemaining: {info['remaining']} tokens"
        if slack_webhook:
            send_slack_alert(msg, slack_webhook)
        print(f"🚨 CRITICAL ALERT SENT: {msg}")
        
    elif info['usage_percentage'] >= 90:
        msg = f"HIGH: Daily budget at {info['usage_percentage']}%\nTeam: {limiter.team_id}\nRemaining: {info['remaining']} tokens"
        if slack_webhook:
            send_slack_alert(msg, slack_webhook)
        print(f"⚠️  HIGH ALERT SENT: {msg}")
        
    elif info['usage_percentage'] >= 80:
        msg = f"MEDIUM: Daily budget at {info['usage_percentage']}%\nTeam: {limiter.team_id}"
        if slack_webhook:
            send_slack_alert(msg, slack_webhook)
        print(f"⚡ MEDIUM ALERT SENT: {msg}")

if __name__ == '__main__':
    monitor_budgets()
```

---

## Teardown

```bash
# Stop Redis container
docker stop redis-rate-limiter
docker rm redis-rate-limiter

# Clean up any local files (optional)
rm -f .env rate_limiter.py api_proxy.py test_rate_limiter.py test_budget_limit.py alerting.py
```

---

## Next Steps

1. **Integrate with your API gateway** — Deploy this as middleware in front of your LLM calls
2. **Add multi-team support** — Extend to track budgets per team/project/API key
3. **Connect to billing systems** — Sync token usage with actual dollar costs
4. **Build a dashboard** — Use Grafana to visualize budget consumption over time
5. **Implement burst allowances** — Allow temporary overrides with approval workflow

---

## Related Techniques

- [M-03: Model Routing](m03-model-router.md) — Combine routing with rate limits for cost control
- [M-06: Observability](m06-observability.md) — Track rate limit events in your observability platform
- [Self-Hosted: Rate Limiting Inference Servers](../self-hosted/s05-rate-limiting.md) — Apply similar patterns to self-hosted models
