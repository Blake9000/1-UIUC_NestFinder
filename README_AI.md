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

### 3.3: Failure Analysis

1. Poor location understanding  
For the input “Find me a place close to Target on Green Street,” none of the returned apartments were actually close to that location. The app may struggle with landmark-based queries.  

2. Incorrect attribute matching  
For the input “I want the cheapest apartment with parking and internet included,” the app matched the parking requirement well, but did not correctly satisfy the internet requirement. The failure shows that the retrieval accuracy is not high enough.


### 3.4: Improvement Attempt
**Prompt improvement**

Prompt to improve: Find me a place close to Target on Green Street.

Reason: The top 3 listings aren't giving apartments that are close to the target or Green St. at all

Improved Prompt: Find the best places near Sixth St. and Green St.


**Before:** 

Before Prompt: Find me a place close to Target on Green Street.

Before Output:

Top 3 listings it gave:
1. 502 E. Stoughton St
2. 1305 W. Columbia Ave
3. 202 E Springfield Ave

Overall: not a good match, these listings aren't near the Target at all, somewhat near Green St. but not entirely accurate

**After**

After Prompt: Find the best places near Sixth St. and Green St.

After Output:
1. 713 S Sixth St
2. 54 E Chalmers St
3. 204 E Clark St

Overall: Still not great, but the first listing is dead on and is very close to Target and Green St.

**Why it Helped:**
This prompt helped because the AI is trained with listing information, since the listings may not have "near Target" as something advertised,
the AI isn't sure where or what Target (the store) is. Thus, specifying street locations near the Target and Green may give better results.
I chose to ask for Sixth St because it is the one perpendicular to where Target is, and it did in fact give an apartment on sixth, and one that is close to the target.
Is it better overall? Not entirely since the other two listings aren't anywhere near what is being asked, but being precise about what the AI is trained on can help find a better result.



