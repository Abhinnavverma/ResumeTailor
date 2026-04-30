import subprocess
import os
import sys

def convert_tex_to_pdf(tex_filepath):
    # Check if the .tex file actually exists where you say it does
    if not os.path.exists(tex_filepath):
        print(f"Error: Could not find '{tex_filepath}'. Make sure the file is in the same folder as this script.")
        return

    print(f"Firing up local LaTeX engine to compile '{tex_filepath}'...")
    
    try:
        # Run pdflatex on the file.
        # '-interaction=nonstopmode' tells the compiler not to freeze and ask for user input if it hits a minor formatting warning.
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filepath],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("SUCCESS: PDF generated!")
        
        # Cleanup: pdflatex leaves behind messy auxiliary files (.aux, .log, .out). This deletes them.
        base_name = os.path.splitext(tex_filepath)[0]
        for ext in ['.aux', '.log', '.out']:
            junk_file = base_name + ext
            if os.path.exists(junk_file):
                os.remove(junk_file)
        print("Cleaned up temporary LaTeX build files.")

    except FileNotFoundError:
        print("\nCRITICAL ERROR: The 'pdflatex' command is not installed or not in your system's PATH.")
        print("Since you are running this locally, you MUST have LaTeX software installed on your machine for Python to use it.")
        print("- Windows: Install MiKTeX (miktex.org)")
        print("- Mac: Install MacTeX (tug.org/mactex)")
        print("- Linux: Run 'sudo apt install texlive-base'")
        sys.exit(1)
        
    except subprocess.CalledProcessError as e:
        print("\nCOMPILATION FAILED: The .tex file has syntax errors.")
        # Prints the exact error from the LaTeX engine so you know what broke
        print(e.stdout.decode('utf-8', errors='ignore'))

if __name__ == "__main__":
    # Change "resume.tex" to whatever your file is actually named
    target_file = "resume.tex"
    convert_tex_to_pdf(target_file)