import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional
from modules.config import load_config

logger = logging.getLogger(__name__)


class JobDatabase:
    def __init__(self, db_path: Path):
        """
        Initialize a connection to the SQLite database.
        """
        self.db_path = db_path
        logger.info("Connecting to SQLite database at %s", db_path)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        logger.info("Connected to database")

    @classmethod
    def from_config(cls, config_path: Path) -> "JobDatabase":
        """
            Factory method that reads the DBPath from the given config file
            and returns an initialized JobDatabase.
        """
        config = load_config(config_path, required_sections=[('database', ['DBPath'])])
        db_path = Path(config['database']['DBPath'])
        return cls(db_path)

    def list_jobs(self) -> List[Dict]:
        """
        Return a list of all jobs in the `jobs` table.
        """
        logger.debug("Fetching all jobs from the database")
        cursor = self.conn.execute("SELECT id, title, job_description FROM job_postings")
        rows = cursor.fetchall()
        logger.info("Fetched %d job(s)", len(rows))
        return [dict(r) for r in rows]

    def get_job_by_id(self, job_id: int) -> Optional[Dict]:
        """
        Return a single job by its ID, or None if not found.
        """
        logger.debug(f"Fetching job with id=%d", job_id)
        cursor = self.conn.execute(
            "SELECT id, title, job_description FROM job_postings WHERE id = ?", (job_id,)
        )
        row = cursor.fetchone()
        if row:
            logger.info("Job %d found", job_id)
            return dict(row)
        else:
            logger.warning("Job %d not found", job_id)
            return None

    def close(self):
        """
        Close the underlying database connection.
        """
        logger.info("Closing database connection")
        self.conn.close()
