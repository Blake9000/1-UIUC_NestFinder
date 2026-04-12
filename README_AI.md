The general overflow would be:
1. the user types a message into the search bar
2. the backend captures the message
3. relevant data is retrieved from the database
4. prompt amd data is sent to LLM for a response
5. System prompt tells the LLM to handle the formatting of the response
6. the json response is then sent to the web app 

**Data Input & Retrieval**:

User data is captured when a user types a message into the search bar in the web app using natural language (e.g., "What apartments allow cats?"). When the user submits the message, the message is sent to the ai model along with data from the database.

**Preprocessing & Prompt Construction**:

Before sent to the LLM, the prompt and data are formatted in a specific string with the system prompt

**Safety Guardrails**:

Rules are set for the LLM in the final prompt instructing the format to restrict broken output.



## A9 Part 3: Evaluation of the Integrated Feature**

### 3.1: Five Realistic App Inputs**
1. I want a pet-friendly studio under $900 near the Engineering Quad.
2. I want the cheapest apartment with parking and internet included.
3. I want a 2-bedroom apartment that has in-unit laundry.
4. Find me a place close to Target on Green Street.
5. Cheap apartments near the Main Quad.

### 3.2: Evaluate Outputs

| Test Input | Expected Behavior | Actual Output        | Quality Notes                                                                                                                       | Latency   |
|---|---|----------------------|-------------------------------------------------------------------------------------------------------------------------------------|-----------|
| I want a studio under $900 near the Engineering Quad. | App should return affordable studio listings near Engineering Quad. | Returned 3 listings. | Mostly relevant, but one was over budget.                                                                                           | Very fast |
| I want the cheapest apartment with parking and internet included. | App should return matching apartments. | Returned 3 listings. | Good match for the parking requirement but not for internet .                                                                       | Very fast |
| I want a 2-bedroom apartment that has in-unit laundry. | App should return matching apartments. | Returned 3 listings. | Only one of the returned listings is a 2-bedroom apartment, but all of the listings meet the requirement of having in-unit laundry. | Very fast |
| Find me a place close to Target on Green Street. | App should return matching apartments. | Returned 3 listings. | Bad match. None of them is close to the target on Green St.                                                                         | Very fast |
| Cheap apartments near the Main Quad. | App should return matching apartments. | Returned 3 listings. | All good match.                                                                                                                     | Very fast |