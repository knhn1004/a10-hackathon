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


class TeeIO:
    """Tee output to both capture buffer and original stream (for Docker logs)."""

    def __init__(self, capture_buffer, original_stream, prefix=""):
        self.capture_buffer = capture_buffer
        self.original_stream = original_stream
        self.prefix = prefix

    def write(self, message):
        """Write to both buffer and original stream."""
        # Write to capture buffer
        self.capture_buffer.write(message)

        # Also write to original stream (visible in docker logs)
        if message:  # Only write non-empty messages
            if self.prefix:
                self.original_stream.write(f"{self.prefix}{message}")
            else:
                self.original_stream.write(message)
            self.original_stream.flush()

        return len(message)

    def flush(self):
        """Flush both streams."""
        self.capture_buffer.flush()
        self.original_stream.flush()

    def getvalue(self):
        """Get value from capture buffer."""
        return self.capture_buffer.getvalue()


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

    # Save original streams
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # Create capture buffers
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    # Create Tee objects that write to both buffer AND Docker stdout
    stdout_tee = TeeIO(stdout_buffer, old_stdout, prefix="[STDOUT] ")
    stderr_tee = TeeIO(stderr_buffer, old_stderr, prefix="[STDERR] ")

    # Store for capturing matplotlib figures
    captured_figures = []

    try:
        # Redirect to tee streams
        sys.stdout = stdout_tee
        sys.stderr = stderr_tee

        # Log code execution start to Docker logs
        old_stdout.write(f"\n{'='*60}\n")
        old_stdout.write("[CODE EXECUTION START]\n")
        old_stdout.write(f"{'='*60}\n")
        old_stdout.flush()

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

        # Log execution completion to Docker logs
        old_stdout.write(f"{'='*60}\n")
        old_stdout.write("[CODE EXECUTION COMPLETE]\n")
        old_stdout.write(f"{'='*60}\n\n")
        old_stdout.flush()

        # Collect stdout output
        stdout_output = stdout_buffer.getvalue()
        if stdout_output:
            results.append({"type": "text", "content": stdout_output})

        # Collect any captured matplotlib figures
        for img_data in captured_figures:
            results.append({"type": "image", "content": img_data})
            # Log image generation to Docker logs
            old_stdout.write(
                f"[IMAGE] Generated matplotlib plot ({len(img_data)} bytes)\n"
            )
            old_stdout.flush()

        # Collect stderr if any
        stderr_output = stderr_buffer.getvalue()
        if stderr_output:
            results.append({"type": "stderr", "content": stderr_output})

        return {"results": results, "status": "success"}

    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Capture error traceback
        error_trace = traceback.format_exc()

        # Log error to Docker logs
        old_stdout.write(f"{'='*60}\n")
        old_stdout.write("[CODE EXECUTION ERROR]\n")
        old_stdout.write(f"{'='*60}\n")
        old_stdout.write(f"{error_trace}\n")
        old_stdout.write(f"{'='*60}\n\n")
        old_stdout.flush()

        results.append({"type": "error", "content": error_trace})

        return {"results": results, "status": "error"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
