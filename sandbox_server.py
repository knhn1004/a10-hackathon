"""
In-Sandbox API Server
Runs inside each Docker container and executes Python code directly.
Designed to be called by LLM agent tools.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import io
import traceback
import base64
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend

app = FastAPI()


class ExecuteRequest(BaseModel):
    code: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/execute")
async def execute_code(request: ExecuteRequest):
    """
    Execute Python code and return results.
    Captures stdout, stderr, and matplotlib plots.
    """
    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")

    results = []

    # Capture stdout
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Store for capturing matplotlib figures
    captured_figures = []

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # Create execution namespace with matplotlib figure capture
        namespace = {
            "__builtins__": __builtins__,
            "_captured_figures": captured_figures,
        }

        # Inject figure capture hook
        exec(
            """
import matplotlib.pyplot as plt
_original_show = plt.show

def _capture_show(*args, **kwargs):
    import io
    import base64
    from matplotlib import pyplot as plt
    
    for fig_num in plt.get_fignums():
        fig = plt.figure(fig_num)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        _captured_figures.append(img_base64)
        plt.close(fig)

plt.show = _capture_show
""",
            namespace,
        )

        # Execute user code
        exec(request.code, namespace)

        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Collect stdout output
        stdout_output = stdout_capture.getvalue()
        if stdout_output:
            results.append({"type": "text", "content": stdout_output})

        # Collect any captured matplotlib figures
        for img_data in captured_figures:
            results.append({"type": "image", "content": img_data})

        # Collect stderr if any
        stderr_output = stderr_capture.getvalue()
        if stderr_output:
            results.append({"type": "stderr", "content": stderr_output})

        return {"results": results, "status": "success"}

    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Capture error traceback
        error_trace = traceback.format_exc()

        results.append({"type": "error", "content": error_trace})

        return {"results": results, "status": "error"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
