import subprocess
import os

MAX_ERROR_CHARS = 1500


def _latex_error_snippet(stdout: bytes | str) -> str:
    if isinstance(stdout, bytes):
        log = stdout.decode("utf-8", errors="ignore")
    else:
        log = stdout or ""

    lines = log.splitlines()
    error_lines = [line for line in lines if line.startswith("!") or line.startswith("l.")]
    snippet = "\n".join(error_lines) if error_lines else log
    snippet = snippet.strip()
    if len(snippet) > MAX_ERROR_CHARS:
        snippet = snippet[-MAX_ERROR_CHARS:]
    return snippet or "No LaTeX log captured."


def convert_tex_to_pdf(tex_filepath):
    if not os.path.exists(tex_filepath):
        raise FileNotFoundError(
            f"Could not find '{tex_filepath}'. Make sure the file is in the same folder as this script."
        )

    print(f"Firing up local LaTeX engine to compile '{tex_filepath}'...")

    try:
        # Run pdflatex on the file.
        # '-interaction=nonstopmode' tells the compiler not to freeze and ask for user input if it hits a minor formatting warning.
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filepath],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
        raise RuntimeError(
            "pdflatex is not installed or not in PATH. "
            "Install MiKTeX (Windows), MacTeX (Mac), or texlive-base (Linux)."
        ) from None

    except subprocess.CalledProcessError as e:
        snippet = _latex_error_snippet(e.stdout)
        print("\nCOMPILATION FAILED: The .tex file has syntax errors.")
        print(e.stdout.decode("utf-8", errors="ignore") if e.stdout else "")
        raise RuntimeError(f"PDF compilation failed:\n{snippet}") from e


if __name__ == "__main__":
    target_file = "resume.tex"
    convert_tex_to_pdf(target_file)
