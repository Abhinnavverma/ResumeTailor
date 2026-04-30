# System Specification: AI-Powered Resume Tuner

## 1. Project Overview
A full-stack web application designed to automatically tailor a base LaTeX resume to a specific Job Description (JD). The system integrates a frontend interface for inputs, a backend orchestrator, the Gemini API for intelligent content modification, and a LaTeX compiler to output a tailored, downloadable PDF.

## 2. Core Assets (Pre-existing)
The backend file system will contain the following static assets:
* `resume.tex`: The base LaTeX template containing the structural foundation of the resume.
* `profile.json`: A comprehensive data file containing all technical backgrounds, achievements, projects, and contact details.
* `convert.py`: A Python script configured to compile a `.tex` file into a PDF using MiKTeX-pdfTeX.

## 3. System Architecture
* **Frontend:** A clean, minimal web interface containing input fields for the **Job Description** and **Company Name**, and a "Generate" button. It handles a loading state while the backend processes the request and provides a download button upon completion.
* **Backend:** A lightweight Python web framework (e.g., FastAPI or Flask) to handle API requests, file I/O operations, LLM communication, and executing sub-processes.
* **LLM Provider:** Google Gemini API (Free Tier).

## 4. The Workflow Pipeline
1.  **Input Submission:** The user pastes the Job Description and Company Name into the frontend and submits the request to the backend endpoint.
2.  **Asset Orchestration:** The backend reads the contents of `resume.tex` and `profile.json`.
3.  **Prompt Construction:** The backend constructs a highly specific prompt combining the JD, Company Name, JSON profile data, and the base `.tex` template, governed by strict constraints (detailed below).
4.  **LLM Execution:** The prompt is sent to the Gemini API. The LLM processes the data and returns *only* the updated LaTeX code.
5.  **File Generation:** The backend writes the LLM's output to a temporary file named `new_resume.tex`.
6.  **Compilation:** The backend invokes `convert.py` (or a subprocess call equivalent to it) to compile `new_resume.tex` into a PDF.
7.  **Output Formatting:** The backend renames the successfully compiled PDF to `Abhinav_verma_[CompanyName].pdf`.
8.  **Delivery:** The generated PDF file is streamed/returned to the frontend endpoint, triggering a download prompt for the user.

## 5. LLM Prompt Constraints (Strict Rules)
The system prompt provided to Gemini must strictly enforce the following rules:
* **Structural Integrity:** The underlying LaTeX structure and formatting of the base resume must remain 100% untouched. Only the text content within the structure may be altered.
* **Keyword Injection:** The resume MUST include all keywords extracted from the target Job Description to maximize ATS compatibility. If a required skill is not found in `profile.json`, it must still be integrated naturally into the text (the user will prepare for these prior to interviews).
* **Truthful Experience:** Strict prohibition on the fabrication of experience. Dates, job titles, and company names must remain factual. However, minor tweaking and re-framing of responsibilities to align with what the JD prioritizes is required.
* **Tone & Phrasing:** The content must exclusively use strong action verbs and maintain a highly impactful, professional tone.
* **Skill Trimming:** Irrelevant technical skills present in the base resume that do not align with or add value to the specific JD must be trimmed out to save space and maintain focus.
* **Length Constraint:** The overall word count of the text content must remain closely aligned with the original base resume's word count to ensure it perfectly fits the physical page layout.
* **Primary Objective:** The overarching goal of the output is to successfully pass both Automated Tracking Systems (ATS) and human Hiring Manager screening.
* **Output Format:** The LLM must output *only* raw, compilable LaTeX code. No markdown formatting, no conversational text, and no explanations.

## 6. Development Instructions for Copilot/AI
* Set up a basic FastAPI backend with CORS enabled.
* Create a simple static HTML/JS frontend that interacts with the backend endpoint.
* Implement a robust system prompt utilizing the constraints listed in Section 5.
* Use `google-generativeai` SDK for the Gemini integration.
* Handle subprocess execution for `python convert.py` securely, capturing standard output and errors to ensure the PDF compiles successfully before responding to the frontend.
* Ensure temporary files (`new_resume.tex`, `.aux`, `.log`) are cleaned up after the PDF is generated and sent.