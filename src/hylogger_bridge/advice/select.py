# Purpose: choose the advice provider at startup; a requested model is never replaced by fixtures.
import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from hylogger_bridge.advice.provider import FixtureProvider, ModelProvider, Provider

Loader = Callable[[Path], Provider]


class StartupError(Exception):
    """The requested provider cannot start, so the service must not start either."""


def add_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model-python",
        type=Path,
        default=None,
        help="optional separate interpreter for local model inference (requires --model)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="a verified local model folder; without it, labelled fixture advice is used",
    )


def _local(folder: Path) -> Provider:
    # Imported here so a service started without --model never loads any model code.
    from hylogger_bridge.advice.local import LocalProvider

    return LocalProvider(folder)


def select(model: Path | None, load: Loader | None = None) -> Provider:
    """The fixture when no model is asked for; otherwise that model or a clear failure."""
    if model is None:
        return FixtureProvider()
    if not model.is_dir():
        raise StartupError(f"model folder not found: {model}")
    try:
        return (load or _local)(model)
    except ImportError as error:
        raise StartupError(
            f"model runtime unavailable ({error}); install the model environment, or start "
            "without --model to use labelled fixture advice"
        ) from error
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise StartupError(
            f"model at {model} cannot be used ({type(error).__name__}: {error})"
        ) from error


def describe(provider: Provider) -> str:
    if isinstance(provider, ModelProvider):
        return (
            f"local model {provider.version} (training data origin: {provider.data_origin}; "
            "advice only, never an authorisation)"
        )
    if isinstance(provider, FixtureProvider):
        return "fixture (labelled stand-in: no model is consulted)"
    return type(provider).__name__


def startup(model: Path | None, load: Loader | None = None, python: Path | None = None) -> Provider:
    """What both launchers call: select, announce on stderr, or exit with the reason."""
    try:
        if python is not None:
            if model is None:
                raise StartupError("--model-python requires --model")
            from hylogger_bridge.advice.process import ProcessProvider

            interpreter = python

            def separate(folder: Path) -> Provider:
                return ProcessProvider(folder, interpreter)

            load = separate
        provider = select(model, load)
    except StartupError as error:
        raise SystemExit(f"error: {error}") from error
    print(f"Advice provider: {describe(provider)}", file=sys.stderr, flush=True)
    return provider
