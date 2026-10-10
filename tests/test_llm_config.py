import os
import subprocess
import sys


def test_llm_defaults_match_production_baseline():
    env = os.environ.copy()
    env.pop("OLLAMA_MODEL", None)
    env.pop("OLLAMA_TIMEOUT_SECONDS", None)

    code = """
import os
from unittest.mock import patch

with patch("dotenv.load_dotenv", return_value=False):
    import llm.config as config
    print(config.OLLAMA_MODEL)
    print(config.OLLAMA_TIMEOUT_SECONDS)
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = result.stdout.strip().splitlines()

    assert lines == ["qwen3:4b-instruct", "300.0"]
