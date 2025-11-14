"""Example usage of Character Creation Pipeline.

This script demonstrates how to create characters with AI-generated
speaking styles and appearances using async operations for better performance.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules import CharacterCreationPipeline


async def main():
    print("=" * 60)
    print("Character Creation Pipeline Example")
    print("=" * 60)
    print()

    # Initialize the pipeline
    pipeline = CharacterCreationPipeline()

    # Get available tags
    print("Available Tags:")
    tags = pipeline.get_available_tags()
    for category, options in tags.items():
        print(f"  {category}: {', '.join(options)}")
    print()

    # Example 1: Software Engineer character
    print("-" * 60)
    print("Example 1: Creating a software engineer character...")
    print("-" * 60)

    character1 = await pipeline.create_character(
        name="Alice Chen",
        occupation="Senior Software Engineer",
        age=28,
        gender="Female",
        tags={
            "relationship": "co-worker",
            "tone": "casual",
            "characteristics": "humorous"
        },
        temperature=0.7
    )

    if character1["success"]:
        print(f"\n✅ Character created successfully!\n")
        print(f"Name: {character1['name']}")
        print(f"Occupation: {character1['occupation']}")
        print(f"Age: {character1['age']}")
        print(f"Gender: {character1['gender']}")
        print(f"\nSpeaking Style:")
        print(f"{character1['speaking_style']}\n")
        print(f"Appearance:")
        print(f"{character1['appearance']}\n")
    else:
        print(f"\n❌ Failed to create character:")
        for error in character1["errors"]:
            print(f"  - {error}")

    # Example 2: Teacher character
    print("-" * 60)
    print("Example 2: Creating a teacher character...")
    print("-" * 60)

    character2 = await pipeline.create_character(
        name="Dr. Robert Martinez",
        occupation="University Professor",
        age=45,
        gender="Male",
        tags={
            "relationship": "friend",
            "tone": "formal",
            "characteristics": "empathetic"
        },
        temperature=0.7
    )

    if character2["success"]:
        print(f"\n✅ Character created successfully!\n")
        print(f"Name: {character2['name']}")
        print(f"Occupation: {character2['occupation']}")
        print(f"Age: {character2['age']}")
        print(f"Gender: {character2['gender']}")
        print(f"\nSpeaking Style:")
        print(f"{character2['speaking_style']}\n")
        print(f"Appearance:")
        print(f"{character2['appearance']}\n")
    else:
        print(f"\n❌ Failed to create character:")
        for error in character2["errors"]:
            print(f"  - {error}")

    # Example 3: Batch creation
    print("-" * 60)
    print("Example 3: Creating multiple characters in batch...")
    print("-" * 60)

    characters_to_create = [
        {
            "name": "Sarah Kim",
            "occupation": "Graphic Designer",
            "age": 24,
            "gender": "Female",
            "tags": {
                "relationship": "friend",
                "tone": "casual",
                "characteristics": "humorous"
            }
        },
        {
            "name": "James Wilson",
            "occupation": "Marketing Manager",
            "age": 35,
            "gender": "Male",
            "tags": {
                "relationship": "co-worker",
                "tone": "formal",
                "characteristics": "empathetic"
            }
        }
    ]

    results = await pipeline.create_batch_characters(characters_to_create)

    print(f"\n✅ Created {len(results)} characters in parallel:\n")
    for i, char in enumerate(results, 1):
        if char["success"]:
            print(f"{i}. {char['name']} - {char['occupation']}")
        else:
            print(f"{i}. Failed: {char['name']}")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
