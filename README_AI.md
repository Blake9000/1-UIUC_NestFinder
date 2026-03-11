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