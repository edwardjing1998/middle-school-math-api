# common/db.py
import os

import snowflake.connector
from dotenv import load_dotenv


# Loads .env for local development. In OpenShift, injected environment
# variables take precedence because override=False.
load_dotenv(override=False)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def get_snowflake_connection():
    options = {
        "user": required_env("SNOWFLAKE_USER"),
        "password": required_env("SNOWFLAKE_PASSWORD"),
        "account": required_env("SNOWFLAKE_ACCOUNT"),
        "warehouse": os.getenv(
            "SNOWFLAKE_WAREHOUSE",
            "GLOBAL_FINANCE_WAREHOUSE",
        ),
        "database": os.getenv("SNOWFLAKE_DATABASE", "EDU_AI_APP"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "WEBAPP"),
    }

    role = os.getenv("SNOWFLAKE_ROLE", "").strip()
    if role:
        options["role"] = role

    return snowflake.connector.connect(**options)
