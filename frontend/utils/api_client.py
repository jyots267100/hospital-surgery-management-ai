"""Thin requests-based client for the FastAPI backend. Centralizes the base URL,
timeouts, and error handling so Streamlit pages stay focused on UI.
"""
from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 30


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _handle_response(resp: requests.Response):
    if resp.status_code >= 400:
        try:
            body = resp.json()
            detail = body.get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(resp.status_code, detail)
    if resp.status_code == 204:
        return None
    return resp.json()


def get(path: str, params: dict | None = None):
    resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT_SECONDS)
    return _handle_response(resp)


def post(path: str, json: dict | None = None):
    resp = requests.post(f"{API_BASE_URL}{path}", json=json, timeout=TIMEOUT_SECONDS)
    return _handle_response(resp)


def patch(path: str, json: dict | None = None):
    resp = requests.patch(f"{API_BASE_URL}{path}", json=json, timeout=TIMEOUT_SECONDS)
    return _handle_response(resp)


def api_call(method, *args, **kwargs):
    """Wraps a client call, surfacing ApiError as a Streamlit error banner."""
    try:
        return method(*args, **kwargs), None
    except ApiError as exc:
        return None, f"API error ({exc.status_code}): {exc.detail}"
    except requests.RequestException as exc:
        return None, f"Could not reach the API at {API_BASE_URL}: {exc}"


def check_api_health() -> bool:
    try:
        requests.get(f"{API_BASE_URL}/health", timeout=5).raise_for_status()
        return True
    except requests.RequestException:
        return False
