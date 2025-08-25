import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any
from modules.template_processor import TemplateProcessor


@pytest.fixture
def sample_context_data() -> Dict[str, Any]:
    """Fixture providing sample resume data for testing."""
    return {
        "experiences": [
            {
                "company": "Test Company",
                "position": "Test Position",
                "duration": "2020-2023",
                "description": "Test description",
            }
        ],
        "skills": ["Python", "Testing", "Pytest"],
        "education": [
            {
                "institution": "Test University",
                "degree": "Test Degree",
                "graduation": "2020",
            }
        ],
    }

@pytest.fixture
def env_vars(monkeypatch):
    env = {
        "FULLNAME": "Test User",
        "EMAIL": "test@example.com",
        "PHONE": "123-456-7890",
        "LOCATION": "Test City",
        "WEBSITE": "https://example.com",
        "GITHUB": "https://github.com/testuser",
        "LINKEDIN": "https://linkedin.com/in/testuser",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env

@pytest.fixture
def mock_env_file(monkeypatch, tmp_path, env_vars):
    file_env = {k: v for k, v in env_vars.items()}
    p = tmp_path / ".env"
    p.write_text("\n".join(f"{k}={v}" for k, v in file_env.items()) + "\n")

    return str(p)

@pytest.fixture
def mock_template_file(tmp_path):
    """Fixture that creates a mock template file for testing."""
    return Path("test_template.docx")


class TestTemplateProcessor:

    def test_init_with_valid_template(self, mock_template_file, env_vars):
        """Test initializing with a valid template file."""
        processor = TemplateProcessor(mock_template_file)
        assert processor.template_path == mock_template_file
        assert isinstance(processor.context_data, dict)
        assert processor.context_data["FULLNAME"] == "Test User"

    def test_init_with_invalid_template(self):
        """Test initializing with a non-existent template file."""
        with pytest.raises(FileNotFoundError):
            TemplateProcessor("nonexistent_file.docx")

    def test_load_env_values(self, mock_template_file, mock_env_file):
        """Test loading values from environment variables."""
        with patch("pathlib.Path.exists", return_value=True):
            processor = TemplateProcessor(mock_template_file)
            env_values = processor.load_env_values()

            assert env_values["FULLNAME"] == "Test User"
            assert env_values["EMAIL"] == "test@example.com"
            assert "FULLNAME" in processor.context_data

    def test_load_env_values_missing_fullname(self, tmp_path, mock_template_file):
        """Test handling of missing mandatory field."""
        tmp_env = tmp_path / ".env"
        tmp_env.write_text("EMAIL=test@example.com\n")

        # with patch("pathlib.Path.exists", return_value=True):
        with pytest.raises(ValueError, match="Mandatory field 'FULLNAME' not found in .env file"):
            processor = TemplateProcessor(mock_template_file, load_env=False)
            processor.load_env_values(dotenv_path=tmp_env, override=True)

    def test_load_resume_data(self, mock_template_file, sample_context_data):
        """Test loading resume data."""
        processor = TemplateProcessor(mock_template_file)

        # Set up initial context data from env
        initial_context = processor.context_data.copy()

        # Load resume data
        updated_context = processor.load_resume_data(sample_context_data)

        # Check if resume data was added to context
        assert "experiences" in updated_context
        assert updated_context["experiences"] == sample_context_data["experiences"]

        # Check if original env values are preserved
        for key in initial_context:
            assert key in updated_context

    def test_load_template(self, mock_template_file):
        """Test loading the DocxTemplate."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template:
            mock_instance = MagicMock()
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file)
            processor.doc = None  # Reset doc to test load_template directly
            processor.load_template()

            mock_docx_template.assert_called_once_with(mock_template_file)
            assert processor.doc == mock_instance

    def test_get_template_variables(self, mock_template_file):
        """Test retrieving template variables."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template:
            mock_instance = MagicMock()
            mock_instance.get_undeclared_template_variables.return_value = {"FULLNAME", "SKILLS", "EXPERIENCES"}
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file)
            variables = processor.get_template_variables()

            assert variables == {"FULLNAME", "SKILLS", "EXPERIENCES"}
            mock_instance.get_undeclared_template_variables.assert_called_once()

    def test_get_missing_variables(self, mock_template_file):
        """Test identifying missing template variables."""
        with patch.object(TemplateProcessor, "get_template_variables") as mock_get_vars:
            mock_get_vars.return_value = {"FULLNAME", "SKILLS", "MISSING_VAR"}

            processor = TemplateProcessor(mock_template_file)
            processor.context_data = {"FULLNAME": "Test User", "SKILLS": ["Python"]}

            missing = processor.get_missing_variables()
            assert "MISSING_VAR" in missing
            assert "FULLNAME" not in missing
            assert "SKILLS" not in missing

    def test_fill_template(self, mock_template_file):
        """Test filling the template with context data."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template:
            mock_instance = MagicMock()
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file)
            processor.load_template()
            with patch.object(processor, "get_missing_variables", return_value=[]):
                processor.fill_template()

                mock_instance.render.assert_called_once_with(processor.context_data)

    def test_save_docx(self, mock_template_file, tmp_path):
        """Test saving the filled document as docx."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template:
            mock_instance = MagicMock()
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file, output_dir=tmp_path)
            processor.load_template()
            output_path = processor.save_docx("test_output")

            assert output_path == tmp_path / "test_output.docx"
            mock_instance.save.assert_called_once_with(output_path)

    def test_save_docx_file_exists(self, mock_template_file, tmp_path):
        """Test saving docx when file already exists."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template, \
                patch("pathlib.Path.exists", return_value=True), \
                patch("time.time", return_value=12345):
            mock_instance = MagicMock()
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file, output_dir=tmp_path)
            processor.load_template()
            output_path = processor.save_docx("test_output")

            # Should add timestamp to filename
            assert "12345" in output_path.name
            mock_instance.save.assert_called_once()

    def test_save_pdf(self, mock_template_file, tmp_path):
        """Test saving the filled document as PDF."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template, \
                patch("modules.template_processor.docx2pdf.convert") as mock_convert:
            mock_instance = MagicMock()
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file, output_dir=tmp_path)

            # Mock save_docx to return a predictable path
            docx_path = tmp_path / "test_output.docx"
            with patch.object(processor, "save_docx", return_value=docx_path):
                pdf_path = processor.save_pdf("test_output")

                assert pdf_path == tmp_path / "test_output.pdf"
                mock_convert.assert_called_once_with(str(docx_path), str(pdf_path))

    def test_generate_docx(self, mock_template_file, tmp_path):
        """Test generating resume in docx format."""
        processor = TemplateProcessor(mock_template_file, output_dir=tmp_path)

        with patch.object(processor, "fill_template") as mock_fill, \
                patch.object(processor, "save_docx", return_value=Path("test_output.docx")) as mock_save:
            output_path = processor.generate(output_format="docx", output_filename="test")

            mock_fill.assert_called_once()
            mock_save.assert_called_once_with("test")
            assert output_path == Path("test_output.docx")

    def test_generate_pdf(self, mock_template_file, tmp_path):
        """Test generating resume in PDF format."""
        processor = TemplateProcessor(mock_template_file, output_dir=tmp_path)

        with patch.object(processor, "fill_template") as mock_fill, \
                patch.object(processor, "save_pdf", return_value=Path("test_output.pdf")) as mock_save:
            output_path = processor.generate(output_format="pdf", output_filename="test")

            mock_fill.assert_called_once()
            mock_save.assert_called_once_with("test")
            assert output_path == Path("test_output.pdf")


    def test_load_env_values_with_profile_image(self, monkeypatch, tmp_path, mock_template_file, mock_env_file):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test_template.docx").write_bytes(b"")
        (tmp_path / "profile.png").write_bytes(b"")

        processor = TemplateProcessor(mock_template_file, load_env=True)
        env_values = processor.env_values

        assert "PROFILE_PATH" in env_values
        assert env_values["PROFILE_PATH"] == Path("profile.png")


    def test_load_resume_data_with_overrides(self, mock_template_file, sample_context_data):
        """Test loading resume data that overrides env values."""
        # Add an override to the sample data
        override_data = sample_context_data.copy()
        override_data["FULLNAME"] = "Override Name"

        with patch("modules.template_processor.logger.warning") as mock_warning:
            processor = TemplateProcessor(mock_template_file)
            processor.load_resume_data(override_data)

            # Check if warning was logged
            mock_warning.assert_called_with(
                "Resume data overrides the following values from .env: FULLNAME"
            )

            # Check if override was applied
            assert processor.context_data["FULLNAME"] == "Override Name"

    def test_error_during_template_render(self, mock_template_file):
        """Test handling errors during template rendering."""
        with patch("modules.template_processor.DocxTemplate") as mock_docx_template:
            mock_instance = MagicMock()
            mock_instance.render.side_effect = Exception("Rendering error")
            mock_docx_template.return_value = mock_instance

            processor = TemplateProcessor(mock_template_file)
            processor.load_template()

            with pytest.raises(Exception, match="Rendering error"):
                processor.fill_template()