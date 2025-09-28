# Houmy RAG Chatbot - Cost Analysis

## Executive Summary

This document provides a comprehensive cost analysis for the Houmy RAG chatbot system, covering per-request costs, data storage, Google Cloud infrastructure, and additional operational expenses.

## 1. Chat Stream Endpoint Cost Analysis

### 1.1 Per-Request Breakdown (chat_stream endpoint)

The `/chat/stream` endpoint has the following cost components:

#### OpenAI API Costs
| Component | Usage | Rate (2025) | Cost per Request |
|-----------|-------|-------------|------------------|
| **Query Embedding** | ~20 tokens | $0.00013/1K tokens | $0.0000026 |
| **Input Tokens** | ~800 tokens* | $0.15/1M tokens | $0.00012 |
| **Output Tokens (Streaming)** | ~300 tokens | $0.60/1M tokens | $0.00018 |
| **Total OpenAI** | - | - | **$0.0003026** |

*Input includes: system prompt (~200 tokens) + user message (~50 tokens) + RAG context (~550 tokens from 5-10 chunks)

#### Vector Search Operations
| Operation | Provider | Cost per Request |
|-----------|----------|------------------|
| **Supabase pgvector query** | Supabase | $0.0000001 |
| **Embedding generation** | OpenAI | Included above |
| **Total Vector Search** | - | **$0.0000001** |

#### **Total Cost per Chat Stream Request: $0.0003027**

### 1.2 Request Volume Impact

| Daily Requests | Monthly Cost | Annual Cost |
|----------------|--------------|-------------|
| 100 | $0.91 | $10.91 |
| 1,000 | $9.08 | $109.00 |
| 10,000 | $90.81 | $1,089.75 |
| 100,000 | $908.10 | $10,898.25 |
| 1,000,000 | $9,081.00 | $108,982.50 |

### 1.3 Context Size Optimization

The number of retrieved documents significantly impacts costs:

| Context Docs | Input Tokens | Cost per Request | vs. 5 docs |
|--------------|-------------|------------------|------------|
| **5 docs** (default) | ~800 tokens | $0.0003027 | baseline |
| **10 docs** | ~1,350 tokens | $0.0004045 | +33.6% |
| **20 docs** | ~2,450 tokens | $0.0005695 | +88.2% |

## 2. Data Storage Costs (Based on schemas.py)

### 2.1 Database Schema Analysis

Based on the data models in `schemas.py`, the system stores:

#### Primary Data Tables
| Table | Record Size (Est.) | Records/Month (10K users) | Storage Cost/Month |
|-------|-------------------|---------------------------|-------------------|
| **chat_sessions** | 100 bytes | 10,000 | $0.000021 |
| **chat_messages** | 2KB average | 300,000 | $0.0126 |
| **source_metadata** | 500 bytes | 100 books | $0.0000105 |
| **document_chunks** | 1.5KB average | 50,000 chunks | $0.0157 |
| **Total SQLite/Postgres** | - | - | **$0.0283/month** |

#### Vector Embeddings Storage
| Component | Dimensions | Records | Storage | Cost/Month |
|-----------|-----------|---------|---------|------------|
| **Document Embeddings** | 1536 | 50,000 chunks | 306MB | $0.0064 |
| **Session Cache** | 1536 | 10,000 queries | 61MB | $0.0013 |
| **Total Vector Storage** | - | - | 367MB | **$0.0077/month** |

#### File Storage
| Type | Average Size | Quantity | Storage | Cost/Month |
|------|-------------|----------|---------|------------|
| **PDF Books** | 5MB | 100 books | 500MB | $0.0105 |
| **Processed Text** | 1MB | 100 books | 100MB | $0.0021 |
| **Total File Storage** | - | - | 600MB | **$0.0126/month** |

**Total Data Storage Cost: $0.0486/month** (for 10K active users)

## 3. Google Cloud Infrastructure Costs

### 3.1 Cloud Run Service (Primary Application)

Based on `deploy_run.sh` configuration:

| Resource | Configuration | Usage (10K requests/day) | Cost/Month |
|----------|---------------|-------------------------|------------|
| **CPU** | 1 vCPU | ~2 hours/day active | $9.60 |
| **Memory** | 512Mi | ~2 hours/day active | $1.20 |
| **Requests** | 10 concurrent | 300K requests/month | $0.60 |
| **Total Cloud Run** | - | - | **$11.40/month** |

### 3.2 Cloud Build (CI/CD)

| Component | Usage | Rate | Cost/Month |
|-----------|-------|------|------------|
| **Build Minutes** | 20 builds × 5 min | $0.003/minute | $0.30 |
| **Build Storage** | 10GB cache | $0.10/GB/month | $1.00 |
| **Total Cloud Build** | - | - | **$1.30/month** |

### 3.3 Artifact Registry

| Component | Storage | Rate | Cost/Month |
|-----------|---------|------|------------|
| **Docker Images** | 2GB (5 versions) | $0.10/GB/month | $0.20 |
| **Total Artifact Registry** | - | - | **$0.20/month** |

### 3.4 Networking & Load Balancing

| Component | Usage | Rate | Cost/Month |
|-----------|-------|------|------------|
| **Egress Traffic** | 50GB/month | $0.12/GB | $6.00 |
| **Load Balancer** | 1 forwarding rule | $18.25/month | $18.25 |
| **Total Networking** | - | - | **$24.25/month** |

### 3.5 Supabase Database (External)

| Component | Usage | Supabase Plan | Cost/Month |
|-----------|-------|---------------|------------|
| **Database** | 500MB, 2GB transfer | Pro Plan | $25.00 |
| **Storage** | 100GB | Included | $0.00 |
| **Vector Operations** | 300K queries | Included | $0.00 |
| **Total Supabase** | - | - | **$25.00/month** |

**Total Google Cloud + Supabase: $62.15/month**

## 4. Additional Operational Costs

### 4.1 Monitoring & Observability

| Service | Purpose | Cost/Month |
|---------|---------|------------|
| **Google Cloud Monitoring** | System metrics, alerts | $5.00 |
| **Error Tracking (Sentry)** | Error monitoring | $26.00 |
| **Uptime Monitoring** | External monitoring | $10.00 |
| **Total Monitoring** | - | **$41.00/month** |

### 4.2 Security & Compliance

| Service | Purpose | Cost/Month |
|---------|---------|------------|
| **SSL Certificates** | HTTPS encryption | $0.00 (Google managed) |
| **DDoS Protection** | Basic protection | $0.00 (included) |
| **Security Scanning** | Vulnerability assessment | $15.00 |
| **Total Security** | - | **$15.00/month** |

### 4.3 Development & Maintenance

| Component | Purpose | Cost/Month |
|-----------|---------|------------|
| **Development Environment** | Testing/staging | $25.00 |
| **Backup Storage** | Data backup (100GB) | $2.00 |
| **Domain & DNS** | Custom domain | $1.00 |
| **Total Dev/Maintenance** | - | **$28.00/month** |

### 4.4 Third-Party Services

| Service | Purpose | Cost/Month |
|---------|---------|------------|
| **GitHub** | Code repository | $0.00 (public repo) |
| **Docker Hub** | Container registry backup | $0.00 (public images) |
| **Analytics** | Usage analytics | $9.00 |
| **Total Third-Party** | - | **$9.00/month** |

### 4.5 Support & Documentation

| Component | Purpose | Cost/Month |
|-----------|---------|------------|
| **Technical Support** | Google Cloud support | $100.00 |
| **Documentation Hosting** | User guides | $5.00 |
| **Total Support** | - | **$105.00/month** |

## 5. Total Cost Summary

### 5.1 Essential Costs (Minimum Required for Operation)

#### Essential Fixed Costs
| Category | Monthly Cost | Notes |
|----------|-------------|-------|
| **Google Cloud Infrastructure** | $37.15 | Cloud Run, networking, storage |
| **Supabase Database** | $25.00 | Managed PostgreSQL + pgvector |
| **Total Essential Fixed** | **$62.15/month** | Cannot operate without these |

#### Essential Variable Costs (Usage-Based)
| Usage Level | OpenAI Costs | Data Storage | Total Variable | **Total Essential Monthly** |
|-------------|-------------|-------------|----------------|---------------------------|
| **1K requests/day** | $9.08 | $0.05 | $9.13 | **$71.28** |
| **10K requests/day** | $90.81 | $0.49 | $91.30 | **$153.45** |
| **100K requests/day** | $908.10 | $4.86 | $912.96 | **$975.11** |
| **1M requests/day** | $9,081.00 | $48.60 | $9,129.60 | **$9,191.75** |

### 5.2 Optional Costs (Quality of Life & Enterprise Features)

#### Optional Infrastructure & Operations
| Category | Monthly Cost | Purpose | When Needed |
|----------|-------------|---------|-------------|
| **Monitoring & Observability** | $41.00 | Alerts, metrics, error tracking | Production scale (10K+ users) |
| **Security & Compliance** | $15.00 | Vulnerability scanning | Enterprise customers |
| **Development Environment** | $25.00 | Separate staging server | Team development |
| **Backup Storage** | $2.00 | Automated backups | Data protection |
| **Custom Domain** | $1.00 | Professional appearance | Branding |
| **Technical Support** | $100.00 | Google Cloud paid support | Mission-critical |
| **Documentation Hosting** | $5.00 | User guides site | Customer support |
| **Analytics** | $9.00 | Usage analytics | Business insights |
| **Total Optional** | **$198.00/month** | Can operate without these |

### 5.3 Cost Comparison: Essential vs Full-Featured

| Usage Level | Essential Costs | With All Options | Savings |
|-------------|----------------|------------------|---------|
| **1K requests/day** | $71.28 | $269.28 | **$198.00 (74%)** |
| **10K requests/day** | $153.45 | $351.45 | **$198.00 (56%)** |
| **100K requests/day** | $975.11 | $1,173.11 | **$198.00 (17%)** |
| **1M requests/day** | $9,191.75 | $9,389.75 | **$198.00 (2%)** |

### 5.4 Cost Per Request Comparison

#### Essential Cost Per Request
| Usage Level | Fixed Cost/Request | Variable Cost/Request | **Essential Cost/Request** |
|-------------|-------------------|---------------------|--------------------------|
| **1K requests/day** | $2.07 | $0.0003027 | **$2.07** |
| **10K requests/day** | $0.21 | $0.0003027 | **$0.21** |
| **100K requests/day** | $0.021 | $0.0003027 | **$0.021** |
| **1M requests/day** | $0.0021 | $0.0003027 | **$0.0024** |

#### Full-Featured Cost Per Request
| Usage Level | Fixed Cost/Request | Variable Cost/Request | **Total Cost/Request** |
|-------------|-------------------|---------------------|----------------------|
| **1K requests/day** | $8.67 | $0.0003027 | **$8.67** |
| **10K requests/day** | $0.87 | $0.0003027 | **$0.87** |
| **100K requests/day** | $0.087 | $0.0003027 | **$0.087** |
| **1M requests/day** | $0.0087 | $0.0003027 | **$0.009** |

## 6. Cost Optimization Recommendations

### 6.1 Short-Term Optimizations (0-3 months)

1. **Reduce Context Size**: Use 5 documents instead of 10 (saves 33.6% on OpenAI costs)
2. **Implement Response Caching**: Cache similar queries (saves 20-40% on repeat requests)
3. **Optimize Prompts**: Reduce system prompt length (saves 10-15% on input tokens)
4. **Right-size Cloud Run**: Monitor actual usage and adjust CPU/memory

### 6.2 Medium-Term Optimizations (3-12 months)

1. **Implement Smart Routing**: Route simple queries to cheaper models
2. **Add Request Throttling**: Prevent abuse and control costs
3. **Optimize Vector Search**: Use higher relevance thresholds
4. **Database Query Optimization**: Reduce database calls per request

### 6.3 Long-Term Optimizations (12+ months)

1. **Custom Model Training**: Train smaller, specialized models
2. **Edge Computing**: Deploy to Google Cloud CDN for lower latency
3. **Multi-Region Deployment**: Optimize for global users
4. **Advanced Caching**: Implement distributed caching layer

## 7. Break-Even Analysis

### 7.1 Revenue Requirements by Usage Level

#### Essential Costs Only (30% gross margin target)

| Usage Level | Monthly Costs | Required Revenue | Revenue per Request |
|-------------|---------------|------------------|-------------------|
| **1K requests/day** | $71.28 | $237.60 | $7.92 |
| **10K requests/day** | $153.45 | $511.50 | $1.71 |
| **100K requests/day** | $975.11 | $3,250.37 | $1.08 |
| **1M requests/day** | $9,191.75 | $30,639.17 | $1.02 |

#### Full-Featured Costs (30% gross margin target)

| Usage Level | Monthly Costs | Required Revenue | Revenue per Request |
|-------------|---------------|------------------|-------------------|
| **1K requests/day** | $269.28 | $898.27 | $29.94 |
| **10K requests/day** | $351.45 | $1,171.50 | $3.91 |
| **100K requests/day** | $1,173.11 | $3,910.37 | $1.30 |
| **1M requests/day** | $9,389.75 | $31,299.17 | $1.04 |

### 7.2 Pricing Strategy Recommendations

#### For Essential Cost Structure (Most Competitive)
1. **Freemium Model**: 10 requests/day free, $0.05/request after
2. **Subscription Tiers**:
   - Basic: $10/month (200 requests) - 50% margin
   - Pro: $25/month (1000 requests) - 70% margin
   - Enterprise: $200/month (10,000 requests) - 80% margin
3. **Pay-per-use**: $0.02-0.05 per request depending on volume

#### For Full-Featured Structure (Premium Positioning)
1. **Freemium Model**: 5 requests/day free, $0.10/request after
2. **Subscription Tiers**:
   - Basic: $25/month (100 requests) - Premium support included
   - Pro: $100/month (1000 requests) - Full monitoring & analytics
   - Enterprise: $500/month (10,000 requests) - Dedicated support
3. **Pay-per-use**: $0.05-0.15 per request depending on volume

## 8. Key Takeaways

### For Your Current Situation
- **Essential monthly costs**: Only $62.15 + usage
- **At 1K requests/day**: Total cost $71.28/month
- **At 10K requests/day**: Total cost $153.45/month
- **You can save 74% by avoiding optional enterprise features**

### When to Add Optional Features
- **Monitoring**: When you have >1000 active users
- **Development environment**: When you have a team
- **Technical support**: When revenue >$1000/month
- **Security scanning**: When handling sensitive data

This analysis shows you can start lean and scale infrastructure as revenue grows.