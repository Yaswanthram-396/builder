from crewai import Agent, Task, Crew
from textwrap import dedent
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure OPENAI_API_KEY is set
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file.")

normalize_agent = Agent(
    role="Real Estate Data Normalizer",
    goal="Clean and standardize real estate user answers",
    backstory="Fixes human input mistakes, returns normalized terms.",
    verbose=False,
)

def normalize_answer(question, answer):
    task = Task(
        description=dedent(f"""
            Normalize the answer for a structured database.
            Question: "{question}"
            Answer: "{answer}"
            
            Return only a clean answer (no sentences).
        """),
        agent=normalize_agent,
        expected_output="Clean short value like 1200, 2 BHK, 50-75L, Sector 7"
    )

    crew = Crew(agents=[normalize_agent], tasks=[task])
    result = crew.run()
    return result.strip()
