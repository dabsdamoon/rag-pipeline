#!/usr/bin/env python3
import uvicorn
from config import Config

if __name__ == "__main__":
    try:
        Config.validate()
        print("Starting Houmy RAG Chatbot API...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please set up your .env file with the required variables.")
        print("See .env.example for reference.")