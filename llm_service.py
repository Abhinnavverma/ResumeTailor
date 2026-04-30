import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Configure the Groq API client
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

# We'll use Llama-3.3-70b-versatile, which is extremely fast and very capable
MODEL = 'llama-3.3-70b-versatile'

def generate_tailored_resume(job_description: str, company_name: str, base_tex: str, profile_json: str) -> str:
    """
    Sends the resume, profile, and JD to Groq and asks it to return tailored LaTeX code.
    """
    
    system_prompt = f"""You are an expert ATS resume writer and LaTeX engineer. Your goal is to tailor the provided LaTeX resume to perfectly match the provided Job Description (JD) at {company_name}.

STRICT RULES & CONSTRAINTS:
1. STRUCTURAL INTEGRITY: The underlying LaTeX structure, formatting, macros, and section orders MUST remain 100% untouched. DO NOT modify geometry, margins, or documentclass. Only alter the text content within the structural commands.
2. ROLE RETENTION: Do NOT delete entire job roles or positions. You must keep all past roles structurally intact. ONLY rewrite the bullet points under each role to better fit the JD.
3. KEYWORD INJECTION: Naturally seamlessly integrate keywords extracted from the target JD to maximize ATS compatibility. If a skill isn't in the provided profile JSON, weave it naturally into existing experiences anyway.
4. TRUTHFUL EXPERIENCE: Do not fabricate entirely new jobs or degrees. Tweak, reframe, and highlight parts of the existing profile JSON responsibilities to align with the JD priorities. 
5. TONE & PHRASING: Use strong action verbs and maintain a highly impactful, professional tone. Focus on metrics and achievements.
6. SKILL TRIMMING: Trim out technical skills present in the base resume that do NOT align with the specific JD to save space and maintain focused ATS relevance.
7. LENGTH CONSTRAINT: Keep the overall word count closely aligned with the original base resume's length so it fits the physical page layout perfectly (Text Content <= 400 words).
8. OUTPUT FORMAT: YOU MUST OUTPUT ONLY THE RAW, COMPILABLE LATEX CODE. DO NOT wrap the output in markdown code blocks (like ```latex). DO NOT add conversational text before or after. Start immediately with the first line of the LaTeX document and end with \\end{{document}}.
9. SWAP PROJECTS: Swap the current projects with other projects listed under profile.json, which align the closes to the current JD, all the info and the links for the new swapped projects shall work correctly
10. ESCAPE SPECIAL CHARACTERS: Remember to properly escape LaTeX characters like &, %, $ with a backslash (e.g. \\&, \\%, \\$)!"""

    user_prompt = f"""--- DATA INPUTS ---

JOB DESCRIPTION FOR {company_name}:
{job_description}

JSON PROFILE DATA (Source of Truth for achievements and metrics):
{profile_json}

BASE LATEX RESUME TEMPLATE:
{base_tex}"""

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        model=MODEL,
        temperature=0.3, # Low temperature for more deterministic, factual output
    )
    
    text_content = chat_completion.choices[0].message.content
    
    # Strip markdown formatting just in case the model ignores the instruction
    if text_content.startswith("```latex"):
        text_content = text_content[8:]
    elif text_content.startswith("```"):
        text_content = text_content[3:]
        
    if text_content.endswith("```"):
        text_content = text_content[:-3]
        
    return text_content.strip()
