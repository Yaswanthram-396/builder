import os
from openai import OpenAI
from textwrap import dedent

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ai_score_lead(lead):
    """
    Uses GPT-4.1-mini to return (score:int, segment:str, reason:str)
    """

    d = lead.data or {}

    prompt = dedent(f"""
    You are an expert real estate sales agent in India.
    Your job is to QUALIFY a lead based on how serious and complete their information is.

    Lead Type: {lead.lead_type}

    Details:
    - Name: {d.get("name")}
    - Location: {d.get("location") or d.get("location_preference")}
    - BHK: {d.get("bhk")}
    - Area: {d.get("area_sqft") or d.get("area_preference")}
    - Property Type: {d.get("property_type") or d.get("property_type_preference")}
    - Budget / Price: {d.get("price_range") or d.get("budget")}
    - Amenities: {d.get("amenities")}

    Rules for scoring (0–100):
    - More structured & complete answers = higher score.
    - If budget/price/location are missing → heavy penalty.
    - If unrealistic values (e.g. 3 crores budget with no location) → low score.
    - Good engagement or clarity = bonus points.

    Then classify:
    - 80–100  = HOT (contact ASAP)
    - 50–79   = WARM (good lead)
    - 20–49   = COLD (not ready)
    - Below 20 = NONE (reject)

    Return strictly in JSON with keys: score, segment, reason.
    """)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        text = response.choices[0].message.content

        # Expect JSON response
        import json
        result = json.loads(text)

        return (
            int(result.get("score", 0)),
            result.get("segment", "NONE"),
            result.get("reason", "No reason provided.")
        )

    except Exception as e:
        print("❌ GPT Scoring Error:", e)
        # fallback if something fails
        return (0, "NONE", "AI scoring failed.")
