1. Create a base fastapi application using pgvector and setup an index for knn searches.
2. Based on the API interfaces of Alpacas News endpoint and Finnhubs ticker details endpoint create a Sqlalchemy model for Articles that holds all relevant data returned from these endpoints.
3. Create a base langgraph file with two pydantic ai workers, one that researches and another that uses this research to answer a user query. Create a streaming endpoint that uses websockets to stream the models output. Use gemini models.
4. Based on the following endpoints create a Chat React component where users interact with the the /chat enpoint and updates are displayed as responses are streamed. Make sure to store all references and display them in a dropdown at the end of the response.
5. Shoudl "thinking" updates that are streamed from this endpoint, for example "Searching for news". This component will also receive a list of ticker symbols and Company names as a parameter, include a autocomplete/suggestion feature that
   suggests tickers based on user inputs after the character '#'.
