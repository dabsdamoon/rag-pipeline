# Character Creation Pipeline

The Character Creation Pipeline is an AI-powered module that generates detailed character profiles including speaking styles and physical appearances based on character attributes and personality tags.

## Overview

This module uses OpenAI's language models to create rich, believable character descriptions that can be used for:
- Interactive storytelling
- Chatbot persona creation
- Game NPC development
- Creative writing assistance

## Features

- **AI-Generated Descriptions**: Uses GPT models to create unique character traits
- **Async/Parallel Processing**: Speaking style and appearance generated in parallel for 2x faster performance
- **Tag-Based Customization**: Personality and style defined through configurable tags
- **Batch Processing**: Create multiple characters in parallel for maximum efficiency
- **Validation**: Input validation with helpful error messages
- **Configurable**: Adjust temperature and model for different creative outputs

## Usage

### Python API

```python
import asyncio
from modules import CharacterCreationPipeline

async def create_my_character():
    # Initialize the pipeline
    pipeline = CharacterCreationPipeline()

    # Create a character (speaking style and appearance generated in parallel)
    character = await pipeline.create_character(
        name="Alice Chen",
        occupation="Software Engineer",
        age=28,
        gender="Female",
        tags={
            "relationship": "co-worker",
            "tone": "casual",
            "characteristics": "humorous"
        },
        temperature=0.7
    )

    if character["success"]:
        print(f"Speaking Style: {character['speaking_style']}")
        print(f"Appearance: {character['appearance']}")
    else:
        print(f"Errors: {character['errors']}")

# Run the async function
asyncio.run(create_my_character())
```

### REST API

#### Get Available Tags

```bash
GET /character/tags
```

**Response:**
```json
{
  "relationship": ["friend", "co-worker"],
  "tone": ["formal", "casual"],
  "characteristics": ["humorous", "tsundere", "empathetic"]
}
```

#### Create a Character

```bash
POST /character/create
```

**Request Body:**
```json
{
  "name": "Alice Chen",
  "occupation": "Software Engineer",
  "age": 28,
  "gender": "Female",
  "tags": {
    "relationship": "co-worker",
    "tone": "casual",
    "characteristics": "humorous"
  },
  "model": "gpt-4o-mini",
  "temperature": 0.7
}
```

**Response:**
```json
{
  "name": "Alice Chen",
  "occupation": "Software Engineer",
  "age": 28,
  "gender": "Female",
  "tags": {
    "relationship": "co-worker",
    "tone": "casual",
    "characteristics": "humorous"
  },
  "speaking_style": "Alice's speech is characterized by...",
  "appearance": "Alice stands at average height with...",
  "success": true,
  "errors": []
}
```

## Character Attributes

### Required Fields

- **name** (string): Character's full name
- **occupation** (string): Character's profession or role
- **age** (integer): Character's age (1-150)
- **gender** (string): Character's gender identity
- **tags** (object): Personality and style tags

### Tags

Tags are defined in `assets/dict_tags.json`:

#### relationship
Defines the relationship between the character and the user:
- `friend` - Friendly, casual relationship
- `co-worker` - Professional colleague relationship

#### tone
Communication style:
- `formal` - Professional, polite communication
- `casual` - Relaxed, informal communication

#### characteristics
Personality traits:
- `humorous` - Witty and funny
- `tsundere` - Initially cold but gradually warm
- `empathetic` - Understanding and compassionate

## Generated Outputs

### Speaking Style

The generated speaking style description includes:
- Sentence structure (short/long, formal/casual)
- Common phrases or verbal habits
- How personality and occupation influence speech
- Unique linguistic quirks

**Example Output:**
```
Alice tends to speak in short, punchy sentences that reflect her analytical
mindset as a software engineer. She peppers her conversation with tech metaphors
like "let's debug that" or "404: excuse not found," showcasing her humorous side.
Her casual tone with co-workers puts people at ease, though she can pivot to
more technical jargon when discussing projects. She often asks clarifying
questions, demonstrating both her thoroughness and her collaborative nature.
```

### Appearance

The generated appearance description includes:
- Overall build and stature
- Facial features and expressions
- Hair style and color
- Typical clothing style
- Distinctive physical traits
- How appearance reflects personality

**Example Output:**
```
Alice stands at 5'6" with a lean, athletic build from her regular weekend
hiking trips. She has warm brown eyes that light up when she's excited about
a problem to solve, and her black hair is usually pulled back in a practical
ponytail. Her style is smart-casual tech startup chic: dark jeans, comfortable
sneakers, and witty programmer t-shirts under an open flannel. She has an
infectious smile that appears often, especially when cracking jokes, and
her animated hand gestures when explaining concepts reveal her enthusiasm
for her work.
```

## Configuration

### Model Selection

You can choose different OpenAI models:

- **gpt-4o-mini** (default) - Fast and cost-effective
- **gpt-4o** - Higher quality, more creative outputs
- **gpt-3.5-turbo** - Faster, good for batch processing

### Temperature

Control creativity (0.0 - 1.0):

- **0.0-0.3** - More focused, consistent outputs
- **0.4-0.7** - Balanced creativity (default: 0.7)
- **0.8-1.0** - More diverse, creative outputs

## Adding Custom Tags

To add custom tags, edit `assets/dict_tags.json`:

```json
{
  "relationship": ["friend", "co-worker", "mentor"],
  "tone": ["formal", "casual", "playful"],
  "characteristics": ["humorous", "tsundere", "empathetic", "mysterious"]
}
```

After modifying the tags file, restart the server to load the new tags.

## Batch Processing

Create multiple characters efficiently in parallel:

```python
import asyncio
from modules import CharacterCreationPipeline

async def create_batch():
    pipeline = CharacterCreationPipeline()

    characters = [
        {
            "name": "Alice",
            "occupation": "Engineer",
            "age": 28,
            "gender": "Female",
            "tags": {"relationship": "co-worker", "tone": "casual", "characteristics": "humorous"}
        },
        {
            "name": "Bob",
            "occupation": "Designer",
            "age": 32,
            "gender": "Male",
            "tags": {"relationship": "friend", "tone": "formal", "characteristics": "empathetic"}
        }
    ]

    # All characters created in parallel for maximum performance
    results = await pipeline.create_batch_characters(characters)
    return results

asyncio.run(create_batch())
```

## Error Handling

The pipeline performs comprehensive validation:

```python
character = pipeline.create_character(
    name="",  # Empty name
    occupation="Engineer",
    age=200,  # Invalid age
    gender="Female",
    tags={
        "relationship": "invalid_value"  # Invalid tag
    }
)

print(character["errors"])
# [
#   "Name is required",
#   "Age must be between 1 and 150",
#   "Tag validation error for 'relationship': Invalid value..."
# ]
```

## Examples

See `examples/character_creation_example.py` for complete usage examples.

```bash
python examples/character_creation_example.py
```

## Integration with RAG Pipeline

Characters created with this pipeline can be used as system prompts in the RAG chatbot to create persona-driven conversations. The speaking style and appearance can inform the chatbot's response generation.

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/character/tags` | GET | Get available tag options |
| `/character/create` | POST | Create a single character |

## Best Practices

1. **Be Specific**: Provide detailed occupations and clear age/gender for better results
2. **Experiment with Temperature**: Try different values to find the right creativity level
3. **Combine Tags Thoughtfully**: Consider how tags interact (e.g., formal + humorous creates dry humor)
4. **Iterate**: Generate multiple variations and pick the best
5. **Cache Results**: Save generated characters to avoid regeneration costs

## Troubleshooting

### Common Issues

**Problem**: Generated text is too generic
- **Solution**: Increase temperature to 0.8-0.9 or provide more specific occupation

**Problem**: Validation errors on tags
- **Solution**: Check `/character/tags` endpoint for available options

**Problem**: API rate limits
- **Solution**: Use batch processing or add delays between requests

## Future Enhancements

Potential improvements:
- Custom tag categories
- Character image generation integration
- Personality consistency scoring
- Multi-language support
- Character relationship mapping
