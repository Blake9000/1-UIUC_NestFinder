## 3.1: Define Five System Scenarios

| Scenario | Description |
|---|---|
| Normal Operation | Regular user traffic with simple apartment search requests, such as asking for cheap apartments or apartments with 2 bedrooms. |
| Peak Usage Hours | Many users access the system at the same time, such as during housing search season, causing a spike in total requests. |
| High-Complexity Queries | Users submit detailed or multi-constraint prompts, such as asking for apartments near campus, within a certain price range, pet-friendly, and available in a specific month. |
| Prompt Injection or Irrelevant Requests | Users submit requests unrelated to apartment recommendations, such as asking for recipes, poems, or code instead of apartment suggestions. |
| System Overload / Cost Optimization | The server experiences high load or the number of expensive API calls becomes too high, so the system must reduce costs and preserve response speed. |


## 3.2: Design Routing Strategies

| Scenario | Routing Strategy | Local Models Used | Hugging Face Model Used | Expected Benefit |
|---|---|---|---|---|
| Normal Operation | Route standard apartment recommendation requests to a lightweight local model first. If the prompt is short and straightforward, use the local model only. | Small local model for basic filtering and ranking | Not used unless fallback is needed | Fast response time and low cost for everyday traffic |
| Peak Usage Hours | During high traffic, send simple queries to the small local model and reserve larger models or APIs only for difficult prompts. | Small local model for most requests | Medium-sized Hugging Face model only for more difficult cases | Prevents bottlenecks and allows more users to be served at once |
| High-Complexity Queries | Detect longer prompts, multiple constraints, or ambiguous requests, then route them to a stronger model that can better interpret user intent before ranking apartments. | Local preprocessing model for keyword extraction or constraint detection | Larger Hugging Face instruction model for reasoning over user preferences | Better recommendation quality for difficult requests |
| Prompt Injection or Irrelevant Requests | First pass the input through a lightweight guardrail or classifier. If the request is unrelated to apartments, block it or return a safe fallback message instead of sending it to the main recommender. | Small local classifier / rule-based filter | Not needed in most cases | Improves safety and prevents wasted computation |
| System Overload / Cost Optimization | When server load is high or daily request volume passes a threshold, force more requests to use local models only and reduce calls to larger external models. | Small or medium local model depending on query complexity | Used only when confidence is very low | Reduces cost and keeps the system stable under heavy load |


## 3.3: Evaluate the Strategy

### 1. How the strategy improves the latency
The routing strategy improves latency by sending simple requests to smaller local models imstead of always using large models. This would allow common requests, such as finding the cheapest apartment, be answered faster. 
It also helps during peak usage hours because the large models are only reserved for complex prompts.

### 2. How the Strategy Reduces Cost
The strategy reduces cost by limiting the use of expensive large models or API calls. Simple requests can be handled by small local models or database filters, which are much cheaper to run. Only difficult requests will be escalated to larger models. 
This helps control total compute cost, especially when it's at peak usage hours.

### 3. How the Strategy Maintains Output Quality
The strategy maintains output quality by routing more complex prompts stronger models that can better understand user intent. In addition, guardrails filter out irrelevant prompts, which keep the models focused on apartment-related tasks.
