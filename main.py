import os
from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import shutil

from llm_service import generate_tailored_resume
from convert import convert_tex_to_pdf

app = FastAPI(title="AI-Powered Resume Tuner")

# Mount the static directory to serve the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

def cleanup_files(filename_base: str):
    """Deletes temporary artifacts like the PDF and TeX files generated per request."""
    # We clean up the specific requested filename and the intermediate new_resume files
    for ext in ['.tex', '.pdf', '.aux', '.log', '.out']:
        file_to_remove = f"new_resume{ext}"
        if os.path.exists(file_to_remove):
            try:
                os.remove(file_to_remove)
            except:
                pass
                
    pdf_to_remove = f"{filename_base}.pdf"
    if os.path.exists(pdf_to_remove):
        try:
            os.remove(pdf_to_remove)
        except:
            pass

@app.post("/generate")
async def generate_resume(
    background_tasks: BackgroundTasks,
    company_name: str = Form(...),
    job_description: str = Form(...)
):
    try:
        # Read the existing foundational files
        with open("resume.tex", "r", encoding="utf-8") as f:
            base_tex = f.read()
            
        with open("profile.json", "r", encoding="utf-8") as f:
            profile_json = f.read()
            
        # 1. Ask LLM to tailor the resume
        new_latex_str = generate_tailored_resume(
            job_description=job_description,
            company_name=company_name,
            base_tex=base_tex,
            profile_json=profile_json
        )
        
        # 2. Write output to temporary file
        temp_tex_file = "new_resume.tex"
        with open(temp_tex_file, "w", encoding="utf-8") as f:
            f.write(new_latex_str)
            
        # 3. Compile the PDF locally (raises RuntimeError with LaTeX log on failure)
        convert_tex_to_pdf(temp_tex_file)
        
        # 4. Rename the output
        clean_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
        final_pdf_name = f"Abhinav_verma_{clean_company_name}.pdf"
        
        # convert_tex_to_pdf outputs to the same name as the tex file: "new_resume.pdf"
        if not os.path.exists("new_resume.pdf"):
            return {"error": "PDF compilation finished without producing new_resume.pdf. Check the server log for pdflatex output."}
        shutil.copy("new_resume.pdf", final_pdf_name)
            
        # 5. Return the file to user and schedule cleanup afterward
        background_tasks.add_task(cleanup_files, f"Abhinav_verma_{clean_company_name}")
        
        return FileResponse(
            path=final_pdf_name, 
            filename=final_pdf_name, 
            media_type="application/pdf"
        )
        
    except Exception as e:
        message = str(e)
        if "rate_limit_exceeded" in message or "Request too large" in message:
            return {
                "error": (
                    "The job description is still too large for Groq's free-tier "
                    "8K tokens-per-minute limit after sending only the sections that change. "
                    "Shorten the JD and try again. "
                    f"Original error: {message}"
                )
            }
        return {"error": message}
