from crewai import Agent, Task, Crew
from textwrap import dedent
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use API key from environment variable
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file.")

# Agent that classifies intent
intent_agent = Agent(
    role="Lead Type Classifier",
    goal="Determine if the user is BUYER or SELLER based on their message",
    backstory="You analyze conversations and label if they want to BUY or SELL property.",
    verbose=False,
)

def classify_intent(text):
    task = Task(
        description=dedent(f"""
            Classify the following text into either BUYER or SELLER.
            Only answer either: BUYER or SELLER.

            Text: "{text}"
        """),
        agent=intent_agent,
        expected_output="BUYER or SELLER"
    )

    crew = Crew(agents=[intent_agent], tasks=[task])
    result = crew.run()
    return result.strip().upper()
