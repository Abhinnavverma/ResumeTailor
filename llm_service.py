import json
import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

MODEL = "qwen/qwen3.6-27b"

# Groq free-tier TPM is 8K and counts prompt + reserved completion tokens.
# Section fragments are much smaller than a full .tex document.
MAX_COMPLETION_TOKENS = 1500

SECTION_ORDER = (
    "preamble",
    "header",
    "headline",
    "experience",
    "achievements",
    "projects",
    "skills",
    "education",
    "closing",
)
MUTABLE_SECTIONS = ("headline", "projects", "skills")
SLIM_PROFILE_KEYS = ("projects", "skills")
PROFILE_DROP_KEYS = ("experience", "education")

SECTION_START_RE = re.compile(r"^% === SECTION: ([a-z_]+) ===\s*$", re.MULTILINE)
GITHUB_URL_RE = re.compile(r"https://github\.com/[^\s}{\\]+")


def parse_resume_sections(tex: str) -> dict[str, str]:
    """Split a marked resume.tex into named section bodies (markers not included)."""
    starts = list(SECTION_START_RE.finditer(tex))
    if not starts:
        raise ValueError("resume.tex is missing section markers (% === SECTION: name ===)")

    sections: dict[str, str] = {}
    sections["preamble"] = tex[: starts[0].start()]

    for i, match in enumerate(starts):
        name = match.group(1)
        end_marker = f"% === END: {name} ==="
        end_idx = tex.find(end_marker, match.end())
        if end_idx == -1:
            raise ValueError(f"Missing end marker for section '{name}'")
        body_start = match.end()
        if body_start < len(tex) and tex[body_start] == "\n":
            body_start += 1
        sections[name] = tex[body_start:end_idx]
        marker_line_end = end_idx + len(end_marker)
        if marker_line_end < len(tex) and tex[marker_line_end] == "\n":
            marker_line_end += 1
        if i + 1 < len(starts):
            continue
        sections["closing"] = tex[marker_line_end:]

    missing = [name for name in SECTION_ORDER if name not in sections]
    if missing:
        raise ValueError(f"resume.tex is missing sections: {', '.join(missing)}")
    return sections


def join_resume_sections(sections: dict[str, str]) -> str:
    """Reassemble a full .tex file from section bodies, restoring markers."""
    missing = [name for name in SECTION_ORDER if name not in sections]
    if missing:
        raise ValueError(f"Cannot join resume; missing sections: {', '.join(missing)}")

    parts = [sections["preamble"]]
    for name in SECTION_ORDER:
        if name in ("preamble", "closing"):
            continue
        parts.append(f"% === SECTION: {name} ===\n")
        parts.append(sections[name])
        parts.append(f"% === END: {name} ===\n")
    parts.append(sections["closing"])
    return "".join(parts)


def slim_profile(profile_json: str) -> dict:
    """Drop experience/education (and unused identity fields) from the Groq payload."""
    try:
        data = json.loads(profile_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"profile.json is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("profile.json must be a JSON object")

    slim = {key: data[key] for key in SLIM_PROFILE_KEYS if key in data}
    leaked = [key for key in PROFILE_DROP_KEYS if key in slim]
    if leaked:
        raise ValueError(f"Slim profile still contains forbidden keys: {leaked}")
    if "projects" not in slim or "skills" not in slim:
        raise ValueError("profile.json must contain projects and skills")
    return slim


def slim_profile_json(profile_json: str) -> str:
    return json.dumps(slim_profile(profile_json), separators=(",", ":"))


def _strip_json_wrappers(text: str) -> str:
    if not text or not text.strip():
        raise ValueError("Model returned empty content")
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _known_projects(profile: dict) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    links: set[str] = set()
    for project in profile.get("projects", []):
        name = project.get("name")
        if name:
            names.add(name)
        link = project.get("githubLink")
        if link:
            links.add(link.rstrip("/"))
    return names, links


def validate_edited_sections(edited: dict, profile: dict) -> dict[str, str]:
    """Require the three mutable LaTeX fragments and reject fabricated projects."""
    if not isinstance(edited, dict):
        raise ValueError("Model output must be a JSON object")

    cleaned: dict[str, str] = {}
    for key in MUTABLE_SECTIONS:
        if key not in edited:
            raise ValueError(f"Model JSON is missing required key '{key}'")
        value = edited[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Model JSON key '{key}' is empty")
        cleaned[key] = value.strip()

    if r"\section{Projects}" not in cleaned["projects"]:
        raise ValueError(r"projects fragment must contain \section{Projects}")
    if r"\section{Technical Skills}" not in cleaned["skills"]:
        raise ValueError(r"skills fragment must contain \section{Technical Skills}")
    if r"\textbf{" not in cleaned["headline"]:
        raise ValueError(r"headline fragment must contain \textbf{...}")

    names, links = _known_projects(profile)
    hrefs = [url.rstrip("/.,;") for url in GITHUB_URL_RE.findall(cleaned["projects"])]
    if hrefs:
        unknown = [url for url in hrefs if url not in links]
        if unknown:
            raise ValueError(
                "projects fragment contains GitHub URLs that are not in profile.json: "
                + ", ".join(unknown)
            )
    elif names and not any(name in cleaned["projects"] for name in names):
        raise ValueError("projects fragment does not reference any project from profile.json")

    return cleaned


def merge_edited_sections(sections: dict[str, str], edited: dict[str, str]) -> dict[str, str]:
    """Replace only headline/projects/skills; keep every other section untouched."""
    merged = dict(sections)
    headline = edited["headline"].strip()
    if r"\end{center}" not in headline:
        headline = headline + "\n\\end{center}"
    merged["headline"] = headline if headline.endswith("\n") else headline + "\n"
    for key in ("projects", "skills"):
        body = edited[key]
        merged[key] = body if body.endswith("\n") else body + "\n"
    return merged


def _parse_model_json(text: str) -> dict:
    stripped = _strip_json_wrappers(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc


def generate_tailored_resume(
    job_description: str, company_name: str, base_tex: str, profile_json: str
) -> str:
    """Ask Groq to rewrite only mutable sections, then join them into a full document."""
    sections = parse_resume_sections(base_tex)
    profile = slim_profile(profile_json)

    system_prompt = f"""You are an expert ATS resume writer and LaTeX engineer. Tailor ONLY the provided LaTeX fragments for a role at {company_name}.

STRICT RULES:
1. Return a JSON object with exactly these keys: headline, projects, skills.
2. Each value must be raw LaTeX using the same macros as the input fragments (resumeProjectHeading, resumeItem, etc.).
3. Do not return a full document. Do not wrap JSON or LaTeX in markdown fences.
4. headline: one role line like \\textbf{{Backend Engineer --- ...}}. Do not include \\begin{{center}} or contact info.
5. projects: keep \\section{{Projects}} and the surrounding list macros. Select exactly 3 projects from the profile JSON that best match the JD. Use each project's real name, githubLink, and techStack. Do not invent jobs, degrees, or GitHub URLs.
6. skills: keep \\section{{Technical Skills}} and trim categories/items that do not match the JD.
7. Do not output experience, education, honors, preamble, or contact sections.
8. Escape LaTeX special characters in new text (\\&, \\%, \\$).
9. Keep length similar to the provided fragments so the resume stays one page."""

    user_prompt = f"""JOB DESCRIPTION FOR {company_name}:
{job_description}

PROFILE CATALOG (projects and skills only):
{json.dumps(profile, separators=(",", ":"))}

CURRENT HEADLINE LATEX:
{sections["headline"]}

CURRENT PROJECTS LATEX:
{sections["projects"]}

CURRENT SKILLS LATEX:
{sections["skills"]}"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL,
            temperature=0.3,
            reasoning_effort="none",
            max_completion_tokens=MAX_COMPLETION_TOKENS,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        message = str(exc)
        if "rate_limit_exceeded" in message or "Request too large" in message:
            raise ValueError(
                "The request exceeded Groq's free-tier 8K tokens-per-minute limit "
                "even after sending only headline/projects/skills. Shorten the job "
                f"description and try again. Original error: {message}"
            ) from exc
        raise

    choice = chat_completion.choices[0]
    if choice.finish_reason == "length":
        raise ValueError(
            "Model output was truncated before the JSON object ended. "
            "Shorten the job description and try again."
        )

    edited = validate_edited_sections(_parse_model_json(choice.message.content), profile)
    merged = merge_edited_sections(sections, edited)
    return join_resume_sections(merged)
