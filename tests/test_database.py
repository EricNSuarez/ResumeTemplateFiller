import sqlite3
import configparser
import logging
import pytest
from modules.database import JobDatabase, ConfigError, load_config

# Enable logging capture in pytest
logging.getLogger("modules.database").setLevel(logging.DEBUG)

@pytest.fixture
def temp_config_and_db(tmp_path):
    """
    Creates:
      - a config file pointing at a temp SQLite DB
      - a SQLite DB with a 'job_postings' table and a single row
    Returns:
      (config_path: Path, db_path: Path, job_record: dict)
    """
    # 1) Prepare paths
    db_path = tmp_path / "job_postings.db"
    config_path = tmp_path / "config"

    # 2) Create SQLite DB and populate
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE job_postings (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            job_description TEXT NOT NULL
        )
    """)
    sample = {"id": 1, "title": "Test Engineer", "job_description": "Test the system."}
    conn.execute(
        "INSERT INTO job_postings (id, title, job_description) VALUES (:id, :title, :job_description)",
        sample
    )
    conn.commit()
    conn.close()

    # 3) Write config
    config = configparser.ConfigParser()
    config['database'] = {'DBPath': str(db_path)}
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)

    yield config_path, db_path, sample

def test_load_config_success(temp_config_and_db):
    config_path, db_path, sample = temp_config_and_db
    cfg = load_config(config_path)
    assert 'database' in cfg
    assert cfg['database']['DBPath'] == str(db_path)

def test_load_config_missing_file(tmp_path):
    missing = tmp_path / "no-such"
    with pytest.raises(ConfigError):
        load_config(missing)

def test_load_config_bad_content(tmp_path):
    cfg_file = tmp_path / "bad"
    # write an empty file
    cfg_file.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(cfg_file)

def test_jobdatabase_from_config_and_queries(temp_config_and_db, caplog):
    config_path, db_path, sample = temp_config_and_db

    # Capture logs
    caplog.set_level(logging.DEBUG)

    # Initialize via from_config
    db = JobDatabase.from_config(config_path)
    assert caplog.records[0].message.startswith("Loading configuration")
    assert caplog.records[-1].message == "Connected to database"

    # Test list_jobs
    jobs = db.list_jobs()
    assert isinstance(jobs, list)
    assert jobs[0]['title'] == sample['title']

    # Test get_job_by_id found
    job = db.get_job_by_id(sample['id'])
    assert job['job_description'] == sample['job_description']

    # Test get_job_by_id not found
    missing = db.get_job_by_id(999)
    assert missing is None

    # Close
    db.close()
    assert db.conn is not None  # still defined, but closed
