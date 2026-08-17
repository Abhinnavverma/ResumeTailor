import json
import unittest
from copy import deepcopy
from pathlib import Path

from llm_service import (
    MUTABLE_SECTIONS,
    join_resume_sections,
    merge_edited_sections,
    parse_resume_sections,
    slim_profile,
    slim_profile_json,
    validate_edited_sections,
)

ROOT = Path(__file__).resolve().parent
RESUME_TEX = (ROOT / "resume.tex").read_text(encoding="utf-8")
PROFILE_JSON = (ROOT / "profile.json").read_text(encoding="utf-8")


class ResumeSectionTests(unittest.TestCase):
    def setUp(self):
        self.sections = parse_resume_sections(RESUME_TEX)
        self.profile = json.loads(PROFILE_JSON)

    def test_parse_real_resume_markers(self):
        for name in (
            "preamble",
            "header",
            "headline",
            "experience",
            "achievements",
            "projects",
            "skills",
            "education",
            "closing",
        ):
            self.assertIn(name, self.sections)
            self.assertTrue(self.sections[name].strip(), msg=f"{name} is empty")

        self.assertIn(r"\documentclass", self.sections["preamble"])
        self.assertIn("Abhinav Verma", self.sections["header"])
        self.assertIn(r"\textbf{", self.sections["headline"])
        self.assertIn("KoinX", self.sections["experience"])
        self.assertIn(r"\section{Projects}", self.sections["projects"])
        self.assertIn(r"\section{Technical Skills}", self.sections["skills"])
        self.assertIn("ABES Engineering College", self.sections["education"])
        self.assertIn(r"\end{document}", self.sections["closing"])

    def test_round_trip_preserves_static_sections(self):
        rebuilt = join_resume_sections(self.sections)
        again = parse_resume_sections(rebuilt)
        for name, body in self.sections.items():
            if name in MUTABLE_SECTIONS:
                continue
            self.assertEqual(again[name], body, msg=f"static section '{name}' changed")

    def test_round_trip_preserves_experience_and_education(self):
        rebuilt = join_resume_sections(self.sections)
        self.assertIn(self.sections["experience"], rebuilt)
        self.assertIn(self.sections["education"], rebuilt)
        self.assertEqual(
            parse_resume_sections(rebuilt)["experience"],
            self.sections["experience"],
        )
        self.assertEqual(
            parse_resume_sections(rebuilt)["education"],
            self.sections["education"],
        )

    def test_slim_profile_drops_experience_and_education(self):
        slim = slim_profile(PROFILE_JSON)
        self.assertNotIn("experience", slim)
        self.assertNotIn("education", slim)
        self.assertIn("projects", slim)
        self.assertIn("skills", slim)
        dumped = slim_profile_json(PROFILE_JSON)
        self.assertNotIn("KoinX Crypto Software", dumped)
        self.assertNotIn("ABES Engineering College", dumped)

    def test_merge_replaces_only_mutable_keys(self):
        original = deepcopy(self.sections)
        edited = {
            "headline": r"\textbf{Platform Engineer --- Kafka \& Golang}",
            "projects": self.sections["projects"].replace("Telescope", "Telescope"),
            "skills": self.sections["skills"].replace("Golang (Primary)", "Golang"),
        }
        edited["projects"] = (
            "\\section{Projects}\n"
            + self.sections["projects"].split("\\section{Projects}", 1)[1]
        )
        merged = merge_edited_sections(self.sections, edited)
        self.assertIn("Platform Engineer", merged["headline"])
        self.assertIn(r"\end{center}", merged["headline"])
        for name, body in original.items():
            if name in MUTABLE_SECTIONS:
                continue
            self.assertEqual(merged[name], body, msg=f"merge mutated '{name}'")

    def test_validate_rejects_missing_keys(self):
        with self.assertRaises(ValueError) as ctx:
            validate_edited_sections({"headline": r"\textbf{X}"}, self.profile)
        self.assertIn("missing required key", str(ctx.exception))

    def test_validate_rejects_wrong_section_headers(self):
        bad_projects = {
            "headline": r"\textbf{Backend Engineer --- Test}",
            "projects": r"\section{Work} not projects",
            "skills": r"\section{Technical Skills} Golang",
        }
        with self.assertRaises(ValueError) as ctx:
            validate_edited_sections(bad_projects, self.profile)
        self.assertIn(r"\section{Projects}", str(ctx.exception))

        bad_skills = {
            "headline": r"\textbf{Backend Engineer --- Test}",
            "projects": r"\section{Projects}" + self.sections["projects"],
            "skills": r"\section{Random} Python",
        }
        with self.assertRaises(ValueError) as ctx:
            validate_edited_sections(bad_skills, self.profile)
        self.assertIn(r"\section{Technical Skills}", str(ctx.exception))

    def test_validate_rejects_unknown_github_url(self):
        fake = {
            "headline": r"\textbf{Backend Engineer --- Test}",
            "projects": (
                r"\section{Projects} \href{https://github.com/not-me/fabricated}{GitHub}"
            ),
            "skills": r"\section{Technical Skills} Golang",
        }
        with self.assertRaises(ValueError) as ctx:
            validate_edited_sections(fake, self.profile)
        self.assertIn("not in profile.json", str(ctx.exception))

    def test_groq_payload_excludes_static_experience_and_stays_small(self):
        slim = slim_profile_json(PROFILE_JSON)
        payload = (
            self.sections["headline"]
            + self.sections["projects"]
            + self.sections["skills"]
            + slim
        )
        self.assertNotIn("Professional Experience", payload)
        self.assertNotIn("KoinX Crypto Software", payload)
        self.assertNotIn("ABES Engineering College", payload)
        self.assertIn("Telescope", payload)
        # Well under Groq's 8k TPM even with a long JD added later.
        self.assertLess(len(payload), 12000)


if __name__ == "__main__":
    unittest.main()
