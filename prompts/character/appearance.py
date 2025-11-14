"""Appearance prompt templates for character creation."""

APPEARANCE_SYSTEM_PROMPT = """You are an expert character designer who creates compelling, believable character descriptions."""


def get_appearance_prompt(
    name: str,
    occupation: str,
    age: int,
    gender: str,
    characteristics: str
) -> str:
    """
    Generate prompt for physical appearance description.

    Args:
        name: Character's name
        occupation: Character's occupation
        age: Character's age
        gender: Character's gender
        characteristics: Personality characteristic (e.g., humorous, empathetic)

    Returns:
        Formatted prompt string
    """

    str_prompt = f"""
    You are a creative character designer. Generate a detailed appearance description for a character with the following attributes:

    Name: {name}
    Occupation: {occupation}
    Age: {age}
    Gender: {gender}
    Personality: {characteristics}

    Describe their physical appearance in 2-3 paragraphs. Include:
    1. Overall build and stature
    2. Facial features and expressions
    3. Hair style and color
    4. Typical clothing style (influenced by their occupation)
    5. Any distinctive physical traits or mannerisms
    6. How their appearance reflects their personality

    Be specific and vivid. Create a visual portrait that brings the character to life.
    """

    return str_prompt