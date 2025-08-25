import os
import logging
import time
from typing import Dict, Any, Optional, Set, List, Union
from pathlib import Path
from docxtpl import DocxTemplate
from dotenv import load_dotenv
import docx2pdf

# Configure logging
logger = logging.getLogger(__name__)


class TemplateProcessor:
    """
    A class to handle docx templates and fill them with resume data.

    Attributes:
        template_path (Path): Path to the docx template file.
        context_data (Dict[str, Any]): Dictionary containing values to fill template placeholders.
        output_dir (Path): Directory to save generated files.
        load_env (bool): Whether to load environment variables. Can be loaded post initialization with 'load_env_values' method.
    """

    def __init__(self, template_path: Union[str, Path], context_data: Optional[Dict[str, Any]] = None,
                 output_dir: Union[str, Path] = None, load_env: bool = True):
        """
        Initialize the TemplateProcessor.

        Args:
            template_path: Path to the docx template file.
            context_data: Data from Resume object to be used for filling the template.
            output_dir: Directory to save generated files (defaults to current directory).
            load_env (bool): Whether to load environment variables. Can be loaded post initialization with 'load_env_values' method.
        """
        self.template_path = Path(template_path)
        self.context_data = {}
        self.env_values = {}
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.doc = None

        logger.info(f"Initializing TemplateProcessor with template: {self.template_path}")

        # Validate template file exists
        if not self.template_path.exists() or not self.template_path.is_file():
            logger.error(f"Template file not found: {self.template_path}")
            raise FileNotFoundError(f"Template file not found: {self.template_path}")

        # Load values from .env file
        if load_env:
            self.load_env_values()

        # Load values from resume_data if provided
        if context_data:
            self.load_resume_data(context_data)


    def load_resume_data(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load values from Resume object.

        Args:
            resume_data: Data from Resume object.

        Returns:
            Updated values dictionary.
        """
        logger.info("Loading resume data")

        # Check for experience data
        if 'experiences' in resume_data and not resume_data['experiences']:
            logger.warning("No experiences found in resume data")

        # Check for overrides
        overrides = set(self.env_values.keys()) & set(resume_data.keys())
        if overrides:
            logger.warning(f"Resume data overrides the following values from .env: {', '.join(overrides)}")

        # Update values with resume data
        self.context_data.update(resume_data)

        logger.info("Successfully loaded resume data")
        return self.context_data

    def load_env_values(self, dotenv_path: Optional[Union[str, Path]] = None, override: bool = False) -> Dict[str, Any]:
        """
        Load values from .env file.

        Args:
            dotenv_path: Path to the .env file. If None, defaults to './.env'.
            override: If True, values from the .env file will override existing environment variables when loaded. Default is False.

        Returns:
            Dictionary containing values from .env file.
        """

        logger.info("Loading values from .env file")

        # Check if .env file exists
        if dotenv_path is None:
            env_path = Path('.env')
        else:
            env_path = Path(dotenv_path)

        if not env_path.exists():
            logger.warning(f"{env_path} file not found")
            return {}

        # Load .env file
        load_dotenv(dotenv_path=env_path, override=override)

        # Get values from environment
        self.env_values = {
            'FULLNAME': os.getenv('FULLNAME'),
            'EMAIL': os.getenv('EMAIL', None),
            'PHONE': os.getenv('PHONE', None),
            'LOCATION': os.getenv('LOCATION', None),
            'WEBSITE': os.getenv('WEBSITE', None),
            'GITHUB': os.getenv('GITHUB', None),
            'LINKEDIN': os.getenv('LINKEDIN', None)
        }

        # Validate mandatory fields
        if not self.env_values.get('FULLNAME'):
            logger.error("Mandatory field 'FULLNAME' not found in .env file")
            raise ValueError("Mandatory field 'FULLNAME' not found in .env file")

        # Check for profile image
        if Path('profile.png').exists():
            self.env_values['PROFILE_PATH'] = Path('profile.png')
        else:
            logger.warning("'profile.png' not found in current directory")

        # Update values
        self.context_data.update(self.env_values)

        logger.info("Successfully loaded values from .env file")
        return self.env_values

    def load_template(self) -> None:
        """
        Load the DocxTemplate object.
        """
        logger.info(f"Loading template: {self.template_path}")
        try:
            self.doc = DocxTemplate(self.template_path)
            logger.info("Template loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            raise

    def get_template_variables(self) -> Set[str]:
        """
        Get all variables in the template.

        Returns:
            Set of variable names found in the template.
        """
        if not self.doc:
            self.load_template()

        variables = self.doc.get_undeclared_template_variables()
        logger.info(f"Template contains {len(variables)} variables")
        return variables

    def get_missing_variables(self) -> List[str]:
        """
        Get variables that are in the template but not in the values.

        Returns:
            List of variable names that are missing values.
        """
        template_vars = self.get_template_variables()
        missing = [var for var in template_vars if var not in self.context_data]

        if missing:
            logger.warning(f"Missing values for {len(missing)} template variables: {', '.join(missing)}")

        return missing

    def fill_template(self) -> None:
        """
        Fill the template with context data.
        """
        if not self.doc:
            logger.error("Template not loaded or filled")
            raise ValueError("Template not loaded or filled")

        logger.info("Filling template with context data")

        # Check for missing variables
        missing = self.get_missing_variables()
        if missing:
            logger.warning(f"Template will have unfilled placeholders for: {', '.join(missing)}")

        # Fill the template
        try:
            self.doc.render(self.context_data)
            logger.info("Template filled successfully")
        except Exception as e:
            logger.error(f"Failed to fill template: {e}")
            raise

    def save_docx(self, output_filename: str = None) -> Path:
        """
        Save the filled document as a docx file.

        Args:
            output_filename: Name of the output file (without extension).

        Returns:
            Path to the saved file.
        """
        if not self.doc:
            logger.error("Template not loaded or filled")
            raise ValueError("Template not loaded or filled")

        # Generate filename if not provided
        if not output_filename:
            output_filename = f"Resume_{self.context_data.get('FULLNAME', 'Unnamed')}"

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create output path
        output_path = self.output_dir / f"{output_filename}.docx"

        # Check if file already exists
        if output_path.exists():
            logger.warning(f"File already exists: {output_path}")
            # Add timestamp to avoid overwriting
            timestamp = Path(output_filename).stem
            output_filename = f"{timestamp}_{int(time.time())}"
            output_path = self.output_dir / f"{output_filename}.docx"

        # Save the document
        try:
            self.doc.save(output_path)
            logger.info(f"Document saved as: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            raise

    def save_pdf(self, output_filename: str = None) -> Path:
        """
        Save the filled document as a PDF file.

        Args:
            output_filename: Name of the output file (without extension).

        Returns:
            Path to the saved PDF file.
        """
        # First save as docx
        docx_path = self.save_docx(output_filename)

        # Create PDF path
        pdf_path = docx_path.with_suffix('.pdf')

        # Check if file already exists
        if pdf_path.exists():
            logger.warning(f"File already exists: {pdf_path}")
            # Add timestamp to avoid overwriting
            timestamp = Path(output_filename or "").stem or "Resume"
            output_filename = f"{timestamp}_{int(time.time())}"
            pdf_path = self.output_dir / f"{output_filename}.pdf"

        # Convert to PDF
        try:
            docx2pdf.convert(str(docx_path), str(pdf_path))
            logger.info(f"Document saved as PDF: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.error(f"Failed to convert to PDF: {e}")
            raise

    def generate(self, output_format: str = 'docx', output_filename: str = None) -> Path:
        """
        Generate the resume by filling the template and saving in the specified format.

        Args:
            output_format: Format to save the document as ('docx' or 'pdf').
            output_filename: Name of the output file (without extension).

        Returns:
            Path to the generated file.
        """
        # Fill the template
        self.fill_template()

        # Save in the specified format
        if output_format.lower() == 'pdf':
            return self.save_pdf(output_filename)
        else:
            return self.save_docx(output_filename)