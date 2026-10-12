"""Shared runtime configuration and handler registry."""
from aiogram import Router
from .settings import Settings
from .storage import PollStore

router = Router()
store: PollStore
settings: Settings
