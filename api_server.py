"""Entry point — run with:  uvicorn api_server:app --reload"""
from src.api import app  # re-export so uvicorn can find `app`

__all__ = ['app']
