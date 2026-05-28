# Vector Database Cost Optimization for RAG Workloads

## Overview
Retrieval-Augmented Generation (RAG) architectures rely on vector databases to store and retrieve embeddings. This guide covers cost optimization strategies for production RAG systems.

## Cost Components

### 1. Storage Costs
- **Vector Storage**: High-dimensional vectors (768-4096 dimensions)
- **Metadata Storage**: Document text, timestamps, tags
- **Index Storage**: HNSW/IVF indices for fast search

### 2. Compute Costs
- **Embedding Generation**: API calls or self-hosted models
- **Query Processing**: CPU/GPU for similarity search
- **Index Building**: Periodic re-indexing

### 3. Operational Costs
- **Data Transfer**: Egress fees for cloud deployments
- **Backup & DR**: Snapshots and replication
- **Monitoring**: Observability stack

## Vector Database Comparison

| Service | Pricing Model | Cost per 1M Vectors | Query Cost | Best For |
|---------|--------------|---------------------|------------|----------|
| Pinecone | Serverless + Pods | $70/mo (starter) | Included | Quick start, low ops |
| Weaviate Cloud | Managed | $25/mo (sandbox) | Included | Hybrid search |
| Qdrant Cloud | Managed | $15/mo (startup) | Included | Performance |
| Milvus (Zilliz) | Managed | $50/mo (basic) | Included | Large scale |
| Self-Hosted (pgvector) | Infrastructure | ~$5/mo (EC2) | $0 | Cost-sensitive |
| Self-Hosted (Qdrant) | Infrastructure | ~$10/mo (EC2) | $0 | Performance/cost |

*Estimates based on 1M vectors, 1536 dimensions, 2024 pricing*

## Optimization Strategies

### Strategy 1: Dimensionality Reduction

**Problem**: Higher dimensions = more storage + slower search

**Solution**: Reduce embedding dimensions while preserving accuracy

```python
from sklearn.decomposition import PCA
import numpy as np

# Original: 1536 dimensions (OpenAI ada-002)
embeddings_original = np.array(embeddings)  # Shape: (N, 1536)

# Reduce to 256 dimensions (83% reduction)
pca = PCA(n_components=256)
embeddings_reduced = pca.fit_transform(embeddings_original)

# Verify accuracy retention
from sklearn.metrics.pairwise import cosine_similarity

# Sample 1000 pairs
sample_indices = np.random.choice(len(embeddings_original), 1000, replace=False)
sim_original = cosine_similarity(
    embeddings_original[sample_indices[:500]],
    embeddings_original[sample_indices[500:]]
)
sim_reduced = cosine_similarity(
    embeddings_reduced[sample_indices[:500]],
    embeddings_reduced[sample_indices[500:]]
)

accuracy = np.corrcoef(sim_original.flatten(), sim_reduced.flatten())[0, 1]
print(f"Similarity correlation: {accuracy:.3f}")  # Typically >0.95
```

**Savings**: 
- Storage: 83% reduction
- Search latency: 40-60% faster
- Trade-off: <2% accuracy loss (often negligible)

### Strategy 2: Quantization

**Problem**: Float32 vectors waste precision for similarity search

**Solution**: Use scalar or product quantization

```python
# Binary Quantization (1 bit per dimension)
def binary_quantize(embeddings):
    return (embeddings > 0).astype(np.int8)

# Original: 1536 * 4 bytes = 6,144 bytes per vector
# Quantized: 1536 * 1 bit = 192 bytes per vector
# Savings: 97% reduction!
```

**Quantization Options**:

| Type | Bits/Dim | Size Reduction | Accuracy Loss |
|------|----------|----------------|---------------|
| Float32 | 32 | 1x (baseline) | 0% |
| Float16 | 16 | 50% | <0.1% |
| Int8 | 8 | 75% | 0.5-1% |
| Binary | 1 | 97% | 3-5% |

**Recommendation**: Start with Int8 for best balance

### Strategy 3: Hierarchical Indexing

**Problem**: Searching 100M vectors is slow and expensive

**Solution**: Two-stage retrieval with coarse filtering

```
┌─────────────────────┐
│   Query Embedding   │
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │ Coarse Filter│  ← Metadata filters (date, category, user)
    │ (SQL/Where)  │     Reduces search space by 90-99%
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ Vector Search│  ← Search only filtered subset
    │ (ANN)        │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │  Re-ranking  │  ← Cross-encoder for top 100
    └─────────────┘
```

**Implementation Example (Qdrant)**:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(host="localhost", port=6333)

results = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="user_id", match=MatchValue(value="user_123")),
            FieldCondition(key="created_at", range={"gte": "2024-01-01"}),
            FieldCondition(key="category", match=MatchValue(value="support"))
        ]
    ),
    limit=10
)
```

**Savings**: 
- Search latency: 10-100x faster
- Compute cost: Proportional reduction

### Strategy 4: Caching Frequent Queries

**Problem**: Repeated queries waste compute and increase latency

**Solution**: Cache query results with TTL

```python
import redis
import hashlib
import json

redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_results(query_embedding, ttl=3600):
    # Hash the embedding for cache key
    query_hash = hashlib.md5(query_embedding.tobytes()).hexdigest()
    cache_key = f"rag:query:{query_hash}"
    
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Perform vector search
    results = vector_search(query_embedding)
    
    # Cache results
    redis_client.setex(cache_key, ttl, json.dumps(results))
    
    return results

# Typical cache hit rates: 30-60% for customer support, 10-20% for search
```

**Savings**:
- Reduced vector DB queries: 30-60%
- Lower latency: <10ms vs 50-200ms
- Cost: Redis is 10x cheaper than vector DB compute

### Strategy 5: Self-Hosting vs. Managed

**Break-Even Analysis**:

| Monthly Vectors | Managed Cost | Self-Hosted Cost | Recommendation |
|-----------------|--------------|------------------|----------------|
| <100K | $0-25/mo | $50/mo (min instance) | ✅ Managed |
| 100K-1M | $25-100/mo | $50-100/mo | ⚖️ Depends on team |
| 1M-10M | $100-500/mo | $100-200/mo | ✅ Self-Hosted |
| 10M+ | $500+/mo | $200-500/mo | ✅ Self-Hosted |

**Self-Hosting Stack (Cost-Optimized)**:

```yaml
# docker-compose.yml
version: '3'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          cpus: '2'

  pgvector:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 2G

volumes:
  qdrant_storage:
  pgdata:
```

**Monthly Infrastructure Cost (AWS)**:
- EC2 t3.large (2 vCPU, 8GB): $60/mo
- EBS gp3 (100GB): $8/mo
- Data transfer: ~$5/mo
- **Total: ~$73/mo** vs $200-500/mo managed

## Monitoring & Alerting

### Key Metrics to Track

1. **Storage Growth Rate**: Vectors added per day
2. **Query Latency P95**: Should be <200ms
3. **Cache Hit Rate**: Target >40%
4. **Recall@K**: Accuracy metric (target >0.90)
5. **Cost per 1K Queries**: Track trend over time

### Prometheus Alerts

```yaml
# prometheus_alerts.yml
groups:
  - name: vector_db_alerts
    rules:
      - alert: HighQueryLatency
        expr: histogram_quantile(0.95, rate(vector_query_latency_bucket[5m])) > 0.2
        for: 5m
        annotations:
          summary: "Vector query P95 latency > 200ms"
          
      - alert: LowCacheHitRate
        expr: rate(cache_hits_total[1h]) / rate(cache_requests_total[1h]) < 0.3
        for: 1h
        annotations:
          summary: "Cache hit rate below 30%"
          
      - alert: StorageGrowthAnomaly
        expr: rate(vector_storage_bytes[24h]) > 1073741824  # 1GB/day
        for: 1d
        annotations:
          summary: "Unusual storage growth rate"
```

## Case Study: Support Bot Optimization

### Before Optimization
- **Vectors**: 5M documents, 1536 dimensions
- **Database**: Pinecone Starter ($70/mo)
- **Query Volume**: 500K/month
- **P95 Latency**: 350ms
- **Monthly Cost**: $70 (DB) + $150 (embedding API) = $220

### After Optimization
1. Applied PCA (1536 → 256 dims)
2. Implemented Int8 quantization
3. Added Redis caching layer
4. Migrated to self-hosted Qdrant

### Results
- **Storage**: 5M vectors, 256 dims, Int8 = 1.2GB (was 30GB)
- **Database**: EC2 t3.large ($60/mo)
- **Cache Hit Rate**: 45%
- **P95 Latency**: 120ms
- **Monthly Cost**: $60 (EC2) + $82 (embedding, 45% cached) = $142

**Savings: $78/mo (35%) + 66% latency improvement**

## Checklist for Cost Optimization

- [ ] Profile current vector dimensions and consider PCA
- [ ] Implement Int8 quantization if accuracy allows
- [ ] Add metadata filters to reduce search space
- [ ] Deploy Redis cache for frequent queries
- [ ] Evaluate managed vs. self-hosted at your scale
- [ ] Set up monitoring for latency and cost metrics
- [ ] Schedule periodic index optimization (vacuum/compact)
- [ ] Review embedding model costs (consider self-hosted)

## Conclusion

Vector database costs can be reduced by 50-80% through careful optimization without sacrificing quality. Start with dimensionality reduction and caching for quick wins, then evaluate self-hosting for long-term savings at scale.
