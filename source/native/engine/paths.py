"""Shared locations for engine sources and generated build files."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def engine_build():
    path = Path(os.environ.get('MONKEY_ENGINE_BUILD', str(PROJECT_ROOT / 'build/engine'))).resolve()
    if not path.is_relative_to((PROJECT_ROOT / 'build').resolve()):
        raise ValueError('Engine outputs must be beneath project build/')
    return path


def artifact_dir(component):
    path = engine_build() / component
    path.mkdir(parents=True, exist_ok=True)
    return path
