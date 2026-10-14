# Purpose: load a complete local decision checkpoint behind the assessment-provider interface.
import importlib
import os
import threading
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.advice.provider import ModelProvider


class LocalProvider(ModelProvider):
    def __init__(self, folder: Path) -> None:
        manifest = verify(folder)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        # The host must call providers outside its database writer transaction.
        api = importlib.import_module("unsloth").FastDecisionModel
        self.model, self.tokenizer = api.from_pretrained(
            model_name=str(folder.resolve()),
            local_files_only=True,
            max_seq_length=manifest["config"]["max_seq_length"],
            load_in_4bit=False,
        )
        api.for_inference(self.model)

        lock = threading.Lock()

        def predict(state: str, questions: dict[str, Any]) -> dict[str, Any]:
            with lock:
                answers: dict[str, Any] = api.predict(self.model, self.tokenizer, state, questions)
            return answers

        super().__init__(predict, manifest["version"], manifest["data_origin"])
