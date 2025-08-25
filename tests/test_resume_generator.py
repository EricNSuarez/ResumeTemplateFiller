import configparser
import logging
import json
import datetime
import pytest
import warnings
import os
from modules.resume_generator import (
    ResumeGenerator,
    Resume,
    Experience,
    load_config,
)

# Enable logging capture in pytest
logging.getLogger("modules.resume_generator").setLevel(logging.DEBUG)


@pytest.fixture
def temp_resume_env(tmp_path):
    """
    Creates:
      - a config file with USER_STORY path, API key, and model
      - a user_story.txt file
      - a prompt file with a minimal working prompt
    Returns:
      (config_path: Path, user_story_path: Path, prompt_path: Path)
    """
    # Paths
    user_story_path = tmp_path / "user_story.txt"
    prompt_path = tmp_path / "prompt.txt"
    config_path = tmp_path / "config"

    # Write user story
    user_story_path.write_text(
        "This is my test user story. I'm a developer with 5 years of Python experience.",
        encoding="utf-8"
    )

    # Minimal working prompt with required placeholders
    minimal_prompt = (
        "Given the following job description:\n{job_description}\n"
        "And the following user story:\n{user_story}\n"
        "Include cover letter: {include_cover_letter}\n"
        "ATS friendly: {ats_friendly}\n"
        "Respond ONLY with valid JSON containing a key 'resume'."
    )
    prompt_path.write_text(minimal_prompt, encoding="utf-8")

    # Get API config from environment with fallbacks
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

    # Write config
    config = configparser.ConfigParser()
    config["user_story"] = {"USER_STORY": str(user_story_path)}
    # API key and model — allow empty if testing skips

    config["api"] = {
        "OPENROUTER_API_KEY": api_key,
        "model": model
    }

    with open(config_path, "w", encoding="utf-8") as f:
        config.write(f)

    yield config_path, user_story_path, prompt_path


def test_read_user_story_success(temp_resume_env):
    config_path, user_story_path, prompt_path = temp_resume_env
    rg = ResumeGenerator(user_story_path, prompt_path, "dummy", "dummy")
    assert rg.read_user_story() == "This is my test user story. I'm a developer with 5 years of Python experience."


def test_read_user_story_missing(temp_resume_env):
    config_path, user_story_path, prompt_path = temp_resume_env
    missing_path = user_story_path.parent / "missing.txt"
    rg = ResumeGenerator(missing_path, prompt_path, "dummy", "dummy")
    with pytest.raises(FileNotFoundError):
        rg.read_user_story()


def test_read_prompt_success(temp_resume_env):
    config_path, user_story_path, prompt_path = temp_resume_env
    rg = ResumeGenerator(user_story_path, prompt_path, "dummy", "dummy")
    assert "{job_description}" in rg.read_prompt()


def test_read_prompt_missing(temp_resume_env):
    config_path, user_story_path, prompt_path = temp_resume_env
    missing_path = prompt_path.parent / "missing.txt"
    rg = ResumeGenerator(user_story_path, missing_path, "dummy", "dummy")
    with pytest.raises(FileNotFoundError):
        rg.read_prompt()


@pytest.mark.timeout(20)
def test_generate_resume_live(temp_resume_env, caplog):
    config_path, user_story_path, prompt_path = temp_resume_env
    cfg = load_config(config_path)

    api_key = cfg["api"].get("OPENROUTER_API_KEY", "").strip()
    model = cfg["api"]["model"]

    if not api_key:
        warnings.warn("No OPENROUTER_API_KEY found in config — skipping live API test")
        pytest.skip("Skipping live API test (no API key)")

    caplog.set_level(logging.DEBUG)

    rg = ResumeGenerator(user_story_path, prompt_path, api_key, model)
    output = rg.generate_resume(
        job_description="Software Engineer position focused on testing.",
        include_cover_letter=False,
        ats_friendly=False
    )

    assert isinstance(output, Resume)
    assert output, "Resume output should not be empty"
    assert any("Generating resume" in r.message for r in caplog.records)
    # TODO: Validate dict keys from output

def test_save_resume_creates_file(tmp_path):
    rg = ResumeGenerator(tmp_path / "story.txt", tmp_path / "prompt.txt", "dummy", "dummy")
    resume_data = Resume(
        summary="Test Summary: Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
        skills=["Python", "Pytest", "Docker", "SQL", "Debugging"],
        experience=[
            Experience(
            role="Senior Backend Tester",
            company="Acme Tech",
            start_date=datetime.datetime.now().date(),
            end_date=datetime.datetime.now().date(),
            achievements=["Write a python test."]
            )
        ]
        )

    output_file = tmp_path / "output.json"

    rg.save_resume(resume_data, output_file)
    assert output_file.exists()
    saved_content = json.loads(output_file.read_text(encoding="utf-8"))

    dump_model = resume_data.model_dump()

    for k in ("start_date", "end_date"):
        for exp in dump_model['experience']:
            exp[k] = exp[k].isoformat()

    assert saved_content == dump_model
