#!/usr/bin/env python3
"""User-run grant of the NOLOGIN revocation writer role to a verified operator."""

from __future__ import annotations

import argparse
import os
import subprocess

import psycopg
from dotenv import load_dotenv

OPERATOR_BY_ENV = {"preview": "cks_preview_migrator", "production": "neondb_owner"}


def grant_release_authorizer(cur, *, environment: str, apply: bool) -> bool:
    """Check or grant membership, requiring the exact environment operator."""
    operator = OPERATOR_BY_ENV[environment]
    cur.execute("SELECT session_user, current_user")
    if cur.fetchone() != (operator, operator):
        raise RuntimeError(
            f"role membership requires exact {environment} identity {operator}"
        )
    cur.execute(
        "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'cks_release_authorizer'"
    )
    role = cur.fetchone()
    if role != (False,):
        raise RuntimeError(
            "cks_release_authorizer is missing or is not a NOLOGIN group"
        )
    cur.execute(
        "SELECT pg_has_role(%s, 'cks_release_authorizer', 'MEMBER')", (operator,)
    )
    is_member = bool(cur.fetchone()[0])
    if apply and not is_member:
        cur.execute(f"GRANT cks_release_authorizer TO {operator}")
        cur.execute(
            "SELECT pg_has_role(%s, 'cks_release_authorizer', 'MEMBER')", (operator,)
        )
        is_member = bool(cur.fetchone()[0])
        if not is_member:
            raise RuntimeError("release-authorizer membership readback failed")
    return is_member


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=tuple(OPERATOR_BY_ENV), required=True)
    parser.add_argument("--expected-code-sha")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.getenv("CFB_ARTIFACT_ENV") != args.environment:
        raise SystemExit("operator environment differs from active artifact context")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required for role membership preflight")
    if args.apply:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], text=True
        ).strip()
        if dirty or head != args.expected_code_sha:
            raise SystemExit("role membership requires reviewed clean committed code")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            member = grant_release_authorizer(
                cur, environment=args.environment, apply=args.apply
            )
        if args.apply:
            conn.commit()
    print(
        {
            "state": "member" if member else "grant_required",
            "environment": args.environment,
        }
    )


if __name__ == "__main__":
    main()
