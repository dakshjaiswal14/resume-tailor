import os
import uuid
import json


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
RESUME_MASTER_DIR = os.path.join(BASE_DIR, "resumes", "master")
RESUME_PARSED_DIR = os.path.join(BASE_DIR, "resumes", "parsed")
RESUME_GENERATED_DIR = os.path.join(BASE_DIR, "resumes", "generated")
RESUME_TEMP_DIR = os.path.join(BASE_DIR, "resumes", "temp")


def ensure_dirs():
    os.makedirs(RESUME_MASTER_DIR, exist_ok=True)
    os.makedirs(RESUME_PARSED_DIR, exist_ok=True)
    os.makedirs(RESUME_GENERATED_DIR, exist_ok=True)
    os.makedirs(RESUME_TEMP_DIR, exist_ok=True)


def generate_resume_id() -> str:
    return f"resume_{uuid.uuid4().hex[:8]}"


def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)