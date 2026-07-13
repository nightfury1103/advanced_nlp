from __future__ import annotations

import os
import subprocess

try:
    import modal
except ModuleNotFoundError:
    modal = None


APP_NAME = "advanced-nlp-qwen25-14b-sentence"
VOLUME_NAME = "advanced-nlp-qwen25-14b-cache"
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-14B-Instruct-AWQ"
SERVED_MODEL_NAME = "qwen25-14b-awq-sentence"
PORT = 8000


def modal_python_packages() -> tuple[str, ...]:
    return (
        "vllm==0.6.6.post1",
        "transformers==4.47.1",
        "accelerate>=1.2.0",
        "huggingface_hub[hf_transfer]>=0.26.0",
    )


if modal is not None:
    app = modal.App(APP_NAME)
    cache_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

    image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git", "curl", "ca-certificates")
        .pip_install(*modal_python_packages())
    )
else:
    app = None
    cache_volume = None
    image = None


def build_vllm_command(
    *,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    served_model_name: str = SERVED_MODEL_NAME,
    port: int = PORT,
) -> list[str]:
    command = [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_name,
        "--served-model-name",
        served_model_name,
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--quantization",
        "awq",
        "--dtype",
        "half",
        "--max-model-len",
        "8192",
        "--gpu-memory-utilization",
        "0.92",
        "--guided-decoding-backend",
        "outlines",
        "--trust-remote-code",
    ]
    if api_key:
        command.extend(["--api-key", api_key])
    return command


if modal is not None:

    @app.function(
        image=image,
        gpu="A100-40GB",
        volumes={"/root/.cache/huggingface": cache_volume},
        timeout=60 * 60,
        secrets=[modal.Secret.from_dotenv()],
    )
    @modal.concurrent(max_inputs=8)
    @modal.web_server(port=PORT, startup_timeout=60 * 20)
    def serve():
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        api_key = os.environ.get("MODEL_API_KEY") or os.environ.get("QWEN_SENTENCE_API_KEY")
        subprocess.Popen(build_vllm_command(api_key=api_key))
