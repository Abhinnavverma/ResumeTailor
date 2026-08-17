import json
import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Configure the Groq API client
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

MODEL = 'qwen/qwen3.6-27b'

# The free tier caps tokens-per-minute at 8000, and Groq counts prompt +
# max_completion_tokens against it. A full resume needs ~2500 output tokens.
MAX_COMPLETION_TOKENS = 3000


def _compact_json(raw: str) -> str:
    """Minify the profile so the prompt leaves room for the full LaTeX response."""
    try:
        return json.dumps(json.loads(raw), separators=(",", ":"))
    except (json.JSONDecodeError, TypeError):
        return raw


def _extract_compilable_latex(text: str) -> str:
    """Strip reasoning/markdown wrappers and keep only a complete LaTeX document."""
    if not text or not text.strip():
        raise ValueError("Model returned empty content")

    text = text.strip()

    # Qwen thinking blocks that can leak into message.content
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Markdown fences (anywhere, not only at the very start/end)
    text = re.sub(r"^```(?:latex|tex)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    start = text.find(r"\documentclass")
    end = text.rfind(r"\end{document}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "Model output did not contain a complete LaTeX document "
            r"(missing \documentclass or \end{document})."
        )

    return text[start:end + len(r"\end{document}")].strip()


def generate_tailored_resume(job_description: str, company_name: str, base_tex: str, profile_json: str) -> str:
    """
    Sends the resume, profile, and JD to Groq and asks it to return tailored LaTeX code.
    """
    
    system_prompt = f"""You are an expert ATS resume writer and LaTeX engineer. Your goal is to tailor the provided LaTeX resume to perfectly match the provided Job Description (JD) at {company_name}.

STRICT RULES & CONSTRAINTS:
1. STRUCTURAL INTEGRITY: The underlying LaTeX structure, formatting, macros, and section orders MUST remain 100% untouched. DO NOT modify geometry, margins, or documentclass. Only alter the text content within the structural commands.
2. ROLE RETENTION: Do NOT delete entire job roles or positions. DO NOT touch anything in experience or its description, EXPERIENCE UNTOUCHED I REPEAT. no content rewrites or anything.
3. KEYWORD INJECTION: Naturally seamlessly integrate keywords extracted from the target JD to maximize ATS compatibility. If a skill isn't in the provided profile JSON, weave it naturally into existing experiences anyway.
4. TRUTHFUL EXPERIENCE: Do not fabricate entirely new jobs or degrees. Tweak, reframe, and highlight parts of the existing profile JSON responsibilities to align with the JD priorities. 
5. TONE & PHRASING: Use strong action verbs and maintain a highly impactful, professional tone. Focus on metrics and achievements.
6. SKILL TRIMMING: Trim out technical skills present in the base resume that do NOT align with the specific JD to save space and maintain focused ATS relevance.
7. LENGTH CONSTRAINT: Keep the overall word count closely aligned with the original base resume's length so it fits the physical page layout perfectly (Text Content <= 400 words).
8. OUTPUT FORMAT: YOU MUST OUTPUT ONLY THE RAW, COMPILABLE LATEX CODE. DO NOT wrap the output in markdown code blocks (like ```latex). DO NOT add conversational text before or after. Start immediately with the first line of the LaTeX document and end with \\end{{document}}.
9. SWAP PROJECTS: Swap the current projects with other projects listed under profile.json, which align the closes to the current JD, all the info and the links for the new swapped projects shall work correctly
10.ESCAPE SPECIAL CHARACTERS: Remember to properly escape LaTeX characters like &, %, $ with a backslash (e.g. \\&, \\%, \\$)!
11.DO NOT MODIFY ANYTHING RELATED TO EXPERIENCE IN THE LATEX CODE IMPORTANT***"""

    user_prompt = f"""--- DATA INPUTS ---

JOB DESCRIPTION FOR {company_name}:
{job_description}

JSON PROFILE DATA (Source of Truth for achievements and metrics):
{_compact_json(profile_json)}

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
        temperature=0.3,  # Low temperature for more deterministic, factual output
        reasoning_effort="none",  # Qwen 3.6 thinks by default; thinking tokens break pdflatex
        max_completion_tokens=MAX_COMPLETION_TOKENS,  # The 2048-token default cuts the document mid-page
    )

    choice = chat_completion.choices[0]
    if choice.finish_reason == "length":
        raise ValueError(
            "Model output was truncated before the document ended. "
            "Shorten the job description or raise max_completion_tokens."
        )

    text_content = choice.message.content
    return _extract_compilable_latex(text_content)
