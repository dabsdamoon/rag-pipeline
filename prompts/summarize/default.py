DEFAULT_SUMMARY_PROMPT = """
Summarize the following conversation between user and assistant in a concise manner, capturing the key points and events.
The summarization does not need to be in full sentences. Rather, it should be in a note-like format, using bullet points or short phrases.

User: {user_message}
Assistant: {assistant_message}
"""