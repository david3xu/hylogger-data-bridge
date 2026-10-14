# Purpose: load a complete local decision checkpoint behind the assessment-provider interface.
import importlib
import os
import threading
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.assets import verify
from hylogger_bridge.advice.encode import VERSION as INPUT_VERSION
from hylogger_bridge.advice.provider import ModelProvider


class LocalProvider(ModelProvider):
    def __init__(self, folder: Path) -> None:
        manifest = verify(folder)
        if manifest["input_version"] != INPUT_VERSION:
            raise ValueError("model input encoding version is incompatible")
        self.action_types = frozenset(manifest["action_types"])
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
                # Use the public encoder as a fit check, not as a teaching record. The dummy
                # target only satisfies that API; it is never trained, persisted or presented.
                option = next(iter(questions["follow_up"]["criteria"]))
                _, report = api.build_dataset(
                    [{"state": state, "questions": questions, "gold": {"follow_up": option}}],
                    self.tokenizer,
                    self.model,
                )
                if report["skipped"] or report.get("truncated", 0):
                    raise ValueError("request exceeds this checkpoint's observed-input budget")
                answers: dict[str, Any] = api.predict(self.model, self.tokenizer, state, questions)
            return answers

        super().__init__(predict, manifest["version"], manifest["data_origin"])

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        if not {item["action_type"] for item in request["candidates"]} <= self.action_types:
            raise ValueError("candidate actions exceed this checkpoint's declared coverage")
        return super().assess(request, at)
