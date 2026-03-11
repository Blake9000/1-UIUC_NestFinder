The general overflow would be:
1. the user types a message into the chatbot
2. the backend captures the message
3. relevant data is retrieved from the database
4. user message and data are formatted into a prompt
5. prompt is sent to LLM
6. the response is checked before sending back to the user

**Data Input**:  
User data will be captured through the chatbot interface in the web app. A user enters a message in natural language, 
such as: "What apartments allow cats?"
When the user submits a message, it is sent from the frontend to the backend. The backend reads the input and then query 
the apartment database. The database information is the main source of the context for the chatbot's response.

**Preprocessing**:  
Before sending the data to LLM, the system will perform basic preprocessing to make the input cleaner for the model to use. 
The system would remove extra spaces and make sure that the user input is not empty.

**Safety Guardrails**:  
The system includes safety guardrails to make the chatbot more reliable. The model is prompted to answer using apartment data 
from the database, which helps reduce made-up information. If the model returns response that is invalid, the app can display a 
fallback message, such as "Sorry, please try again!"