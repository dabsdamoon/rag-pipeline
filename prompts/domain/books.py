BOOKS_PROMPT = """
Please answer the user's question in {language} with following guidelines:

# Context
- Context provided is the prior source of knowledge when communicating.
- Below is the context:
{context}

# Answer Guidelines
- Answer or suggest based on the context and user information. If the question is not related to the context, find the answer from your own knowledge but say it in friendly and conversational tone.
"""