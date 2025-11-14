# Context Engineering vs Prompt Engineering

A practical comparison showing why **what you provide** matters more than **how you ask**.

## Side-by-Side Comparison

### Scenario: User asks "What exercises are safe during pregnancy?"

---

## ❌ Traditional Approach (Prompt Engineering Only)

### Process
```
Vector Search → All 10 Results → Prompt Template → LLM
```

### Context Sent to LLM
```markdown
## Context

Source 1 - BOOK001 (0.92):
Walking and swimming are excellent low-impact exercises during pregnancy. They help maintain cardiovascular health.

Source 2 - BOOK001 (0.85):
Walking and swimming are excellent exercises. Prenatal yoga is also beneficial for flexibility.

Source 3 - BLOG001 (0.45):
I personally found prenatal yoga very relaxing during my pregnancy. My friend Sarah also loved it.

Source 4 - BOOK002 (0.78):
Avoid high-impact activities like running or contact sports during pregnancy.

Source 5 - FORUM01 (0.35):
Has anyone tried yoga? I'm wondering if it's safe.

Source 6 - BOOK001 (0.88):
Swimming and walking are great for pregnant women. Low impact is key.

Source 7 - BLOG002 (0.42):
I did prenatal yoga throughout my pregnancy and felt great!

Source 8 - BOOK003 (0.70):
Strength training with light weights can help maintain muscle tone.

Source 9 - ARTICLE1 (0.55):
Pregnancy exercise guidelines recommend low-impact activities.

Source 10 - BOOK002 (0.68):
Consult your doctor before starting any exercise program during pregnancy.

## Question
What exercises are safe during pregnancy?
```

### Problems
- ❌ **Duplicates**: Sources 1, 2, 6 say the same thing
- ❌ **Low quality**: Forum posts and personal blogs mixed with medical sources
- ❌ **No ranking**: Authoritative sources not prioritized
- ❌ **Token waste**: ~1500 tokens for redundant information
- ❌ **Noise**: Personal anecdotes dilute factual information

### Prompt Engineering Attempt
```
You are a medical expert. Based on the AUTHORITATIVE sources above
(prioritize books and medical sources, ignore blogs and forums),
provide a comprehensive answer...
```

**Result:** Still sends all 10 documents. LLM must figure out what's relevant.

---

## ✅ Modern Approach (Context Engineering)

### Process
```
Vector Search → 10 Results → Context Engineering → 3 Optimized Docs → LLM
```

### Context Engineering Steps

#### 1. Filter (Relevance Threshold: 0.3)
```
10 documents → 9 documents (removed forum post)
```

#### 2. Deduplicate
```
9 documents → 6 documents (removed duplicates)
```

#### 3. Rank (Relevance + Authority)
```
Ranked order:
1. BOOK001 (0.92) ⭐ Medical source
2. BOOK002 (0.78) ⭐ Medical source
3. BOOK003 (0.70) ⭐ Medical source
4. ARTICLE1 (0.55)
5. BLOG001 (0.45)
6. BLOG002 (0.42)
```

#### 4. Assemble (Query Type: Factual → Top 3)
```
6 documents → 3 documents (factual queries need precision)
```

### Context Sent to LLM
```markdown
## Context

Source 1 - Pregnancy Medical Guide (0.92):
Walking and swimming are excellent low-impact exercises during pregnancy. They help maintain cardiovascular health without putting stress on joints.

Source 2 - Medical Handbook for Expectant Mothers (0.78):
Avoid high-impact activities like running or contact sports during pregnancy. Stick to gentle exercises approved by your healthcare provider.

Source 3 - Fitness During Pregnancy (0.70):
Strength training with light weights can help maintain muscle tone during pregnancy. Focus on proper form and avoid heavy lifting.

## Question
What exercises are safe during pregnancy?
```

### Benefits
- ✅ **No duplicates**: Each source provides unique information
- ✅ **High quality**: Only authoritative medical sources
- ✅ **Ranked**: Most relevant and authoritative first
- ✅ **Token efficient**: ~450 tokens (70% reduction)
- ✅ **Signal focused**: No personal anecdotes or noise

### Prompt
```
You are a helpful medical assistant. Answer based on the context above.
```

**Result:** Simple prompt works better with optimized context.

---

## Impact Comparison

| Metric | Prompt Engineering | Context Engineering | Improvement |
|--------|-------------------|---------------------|-------------|
| **Documents to LLM** | 10 | 3 | 70% fewer |
| **Tokens used** | ~1500 | ~450 | 70% reduction |
| **Duplicates** | 3 | 0 | 100% removed |
| **Low-quality sources** | 3 | 0 | 100% filtered |
| **Source ranking** | No | Yes | ✅ Authoritative first |
| **Query adaptation** | No | Yes | ✅ Factual → Top 3 |
| **API cost per query** | $0.0045 | $0.0013 | 71% cheaper |
| **Response quality** | Good | Excellent | ⭐⭐⭐ |

## Real-World Example: Different Query Types

### Query 1: "What is prenatal care?" (Factual)
- **Context Engineering**: Top 3 most relevant documents (precision)
- **Tokens**: ~400
- **Sources**: Medical textbooks

### Query 2: "How does exercise benefit pregnancy?" (Explanatory)
- **Context Engineering**: 5 comprehensive documents (breadth)
- **Tokens**: ~800
- **Sources**: Mix of medical and research

### Query 3: "Should I exercise in third trimester?" (Advisory)
- **Context Engineering**: 4 authoritative documents (trust)
- **Tokens**: ~600
- **Sources**: Medical guidelines first

### Query 4: "Compare yoga vs swimming" (Analytical)
- **Context Engineering**: Diverse sources on each topic
- **Tokens**: ~700
- **Sources**: Balanced representation

## Code Comparison

### Prompt Engineering Approach
```python
# Send everything
results = vector_search(query, limit=10)
prompt = f"""
You are an expert. Based on these {len(results)} sources (prioritize authoritative ones):
{format_sources(results)}
Answer: {query}
"""
response = llm.complete(prompt)
```

### Context Engineering Approach
```python
# Optimize what you send
raw_results = vector_search(query, limit=10)

engineered = context_engineer.engineer_context(
    query=query,
    raw_documents=raw_results,
    source_metadata=metadata,
)

prompt = f"""
Based on the context:
{format_sources(engineered['documents'])}
Answer: {query}
"""
response = llm.complete(prompt)
```

## When to Use Each

### Use Prompt Engineering When:
- ✅ You have 1-2 high-quality sources
- ✅ No duplicates or noise in results
- ✅ Query type doesn't matter
- ✅ Token budget is not a concern

### Use Context Engineering When:
- ✅ Multiple sources with varying quality (**most RAG systems**)
- ✅ Duplicates and redundancy are common
- ✅ Different query types need different strategies
- ✅ Token efficiency matters
- ✅ Source authority varies significantly

## Key Insight

> **Garbage in, garbage out.**
>
> No amount of clever prompting can fix poor context.
> But optimized context works well even with simple prompts.

## Best Practice: Combine Both

1. **Context Engineering** (primary): Optimize what you provide
2. **Prompt Engineering** (secondary): Optimize how you ask

```python
# 1. Engineer the context
optimized_context = context_engineer.engineer_context(...)

# 2. Use appropriate prompt for the task
if query_type == "medical":
    system_prompt = medical_expert_prompt
else:
    system_prompt = general_assistant_prompt

# Best of both worlds
response = llm.complete(system_prompt, optimized_context, query)
```

## Summary

**Context Engineering is to RAG what preprocessing is to Machine Learning.**

Just as you wouldn't train a model on raw, messy data, you shouldn't send raw search results to an LLM.

- **Filter** → Remove noise
- **Deduplicate** → Remove redundancy
- **Rank** → Prioritize quality
- **Compress** → Extract signal
- **Assemble** → Match query type
- **Enrich** → Add metadata

The result: **Better answers, lower costs, happier users.**
