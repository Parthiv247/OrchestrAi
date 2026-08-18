"""Lightweight sync psycopg2 helper for routes that can't use async sessions."""
import os
import psycopg2
from .config import get_settings


def get_sync_conn():
    """Return a raw psycopg2 connection using the same settings as the async engine."""
    s = get_settings()
    return psycopg2.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        dbname=s.postgres_db,
        user=s.postgres_user,
        password=s.postgres_password,
        connect_timeout=10,
    )
