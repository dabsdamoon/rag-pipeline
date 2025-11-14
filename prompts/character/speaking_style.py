"""Speaking style prompt templates for character creation."""

SPEAKING_STYLE_SYSTEM_PROMPT = """
You are an expert character designer who creates compelling, believable characters with distinct voices.
"""


def get_speaking_style_prompt(
    name: str,
    occupation: str,
    age: int,
    gender: str,
    relationship: str,
    tone: str,
    characteristics: str
) -> str:
    """
    Generate prompt for speaking style description.

    Args:
        name: Character's name
        occupation: Character's occupation
        age: Character's age
        gender: Character's gender
        relationship: Relationship with user (e.g., friend, co-worker)
        tone: Communication tone (e.g., formal, casual)
        characteristics: Personality characteristic (e.g., humorous, empathetic)

    Returns:
        Formatted prompt string
    """

    str_prompt = f"""
    You are a creative character designer. Generate a detailed speaking style description for a character with the following attributes:

    Name: {name}
    Occupation: {occupation}
    Age: {age}
    Gender: {gender}
    Relationship with user: {relationship}
    Tone: {tone}
    Characteristics: {characteristics}

    Describe their speaking style in 2-3 paragraphs. Include:
    1. How they structure their sentences (short/long, formal/casual)
    2. Common phrases or verbal habits they might use
    3. How their personality and occupation influence their speech
    4. Any unique linguistic quirks that make them memorable

    Be specific and vivid. Write as if describing to a voice actor.
    """

    return str_prompt