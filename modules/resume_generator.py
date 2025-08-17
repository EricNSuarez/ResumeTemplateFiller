import json
import logging
import configparser
from pathlib import Path
from typing import Dict, List, Any, Optional
from openai import OpenAI
from pydantic import BaseModel, Field
from datetime import date

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config is invalid or missing required fields."""


class ResumeGenerationError(Exception):
    """Raised when resume generation fails."""


class Experience(BaseModel):
    company: str = Field(description="Company name/Organization")
    role: str = Field(description="Job title")
    start_date: date = Field(description="Start date in YYYY-MM format")
    end_date: date = Field(description="End date in YYYY-MM format", default=None)
    achievements: List[str] = Field(default_factory=list, description="List of achievements relevant to the position, including measurable results if available")

class Resume(BaseModel):
    summary: str = Field(description="Brief introduction paragraph tailored to the job", min_length=70)
    skills: List[str] = Field(
        default_factory=list,
        description="List of professional skills/keywords relevant to the position",
        min_length=5
    )
    experience: List[Experience] = Field(
        default_factory=list,
        description="List of experience relevant to the position (most recent first)"
    )
    cover_letter: Optional[str] = Field(description="Tailored cover letter to the job", default=None)


def load_config(config_path: Path) -> configparser.ConfigParser:
    """
    Load and parse the config file.
    Expects at least a [user_story] section with USER_STORY defined.
    """
    logger.debug("Loading configuration from %s", config_path)
    if not config_path.exists():
        logger.error("Config file %s does not exist", config_path)
        raise ConfigError(f"Config file {config_path} not found")

    config = configparser.ConfigParser()
    config.read(config_path)

    if 'user_story' not in config or 'USER_STORY' not in config['user_story']:
        logger.error("Config file %s missing [user_story] section or USER_STORY", config_path)
        raise ConfigError("Missing [user_story] USER_STORY setting")

    logger.info("Configuration loaded successfully")
    return config


class ResumeGenerator:
    def __init__(self, user_story_path: Path, prompt_path: Path, api_key: str, model: str):
        """
        Initialize the resume generator with paths and API configuration.
        """
        self.user_story_path = user_story_path
        self.prompt_path = prompt_path
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")

    @classmethod
    def from_config(cls, config_path: Path, prompt_path: Path, api_key: str, model: str) -> "ResumeGenerator":
        """
        Factory method that reads the USER_STORY path from config file
        and returns an initialized ResumeGenerator.
        """
        config = load_config(config_path)
        user_story_path = Path(config['user_story']['USER_STORY'])
        return cls(user_story_path, prompt_path, api_key, model)

    def read_user_story(self) -> str:
        """
        Read the user story text from file.
        """
        logger.debug("Reading user story from %s", self.user_story_path)
        if not self.user_story_path.exists():
            logger.error("User story file %s not found", self.user_story_path)
            raise FileNotFoundError(f"User story file {self.user_story_path} not found")

        content = self.user_story_path.read_text(encoding="utf-8").strip()
        logger.info("User story loaded successfully (%d characters)", len(content))
        return content

    def read_prompt(self) -> str:
        """
        Read the resume generation prompt from file.
        """
        logger.debug("Reading prompt from %s", self.prompt_path)
        if not self.prompt_path.exists():
            logger.error("Prompt file %s not found", self.prompt_path)
            raise FileNotFoundError(f"Prompt file {self.prompt_path} not found")

        content = self.prompt_path.read_text(encoding="utf-8").strip()
        logger.info("Prompt loaded successfully (%d characters)", len(content))
        return content

    def generate_resume(
        self,
        job_description: str,
        include_cover_letter: bool = False,
        ats_friendly: bool = False
    ) -> Dict[str, Any]:
        """
        Generate resume using the OpenAI client with OpenRouter endpoint.
        """
        logger.info("Generating resume using OpenRouter API")
        user_story = self.read_user_story()
        prompt_template = self.read_prompt()

        # Replace placeholders in the prompt
        prompt_text = prompt_template.format(
            job_description=job_description,
            user_story=user_story,
            include_cover_letter=str(include_cover_letter).lower(),
            ats_friendly=str(ats_friendly).lower()
        )

        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a resume optimization assistant."},
                    {"role": "user", "content": prompt_text}
                ],
                timeout=60,
                temperature=0.5,
                response_format=Resume
            )

            if response.choices[0].message.refusal:
                logger.debug("LLM output was refused: %s...")
                return None
            else:
                parsed_response = response.choices[0].message.parsed
                logger.info("Resume generated successfully")
                return parsed_response

        except (json.JSONDecodeError, AttributeError) as e:
            logger.exception("Failed to parse model output")
            raise ResumeGenerationError(f"Error parsing resume output: {e}")
        except Exception as e:
            logger.exception("Failed to generate resume")
            raise ResumeGenerationError(f"Error generating resume: {e}")

    @staticmethod
    def save_resume(resume_data: Resume, output_path: Path):
        """
        Save the generated resume JSON to a file.
        """
        logger.debug("Saving resume to %s", output_path)
        # TODO: Handle date objects correctly, instead of defaulting to str
        output_path.write_text(json.dumps(resume_data.model_dump(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        logger.info("Resume saved successfully at %s", output_path)
