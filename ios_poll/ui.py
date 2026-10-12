"""Telegram inline keyboards and public results formatting."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from .storage import CHOICES

def voter_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'🍎' if choice == 'ios' else '🤖' if choice == 'android' else '📱'} {label}",
                              callback_data=f"vote:{session_id}:{choice}")]
        for choice, label in CHOICES.items()
    ])


def admin_keyboard(status: str, session_id: int | None) -> InlineKeyboardMarkup:
    if status == "OPEN":
        rows = [
            [InlineKeyboardButton(text="📊 Результаты", callback_data="adm:stats")],
            [InlineKeyboardButton(text="⏹ Завершить", callback_data=f"adm:confirm:{session_id}")],
        ]
    else:
        rows = [[InlineKeyboardButton(text="▶️ Начать новый раунд", callback_data="adm:start")],
                [InlineKeyboardButton(text="📊 Результаты", callback_data="adm:stats")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_results(snapshot: dict) -> str:
    lines = [f"📊 Голосов: {snapshot['total']}"]
    for choice, label in CHOICES.items():
        result = snapshot["results"][choice]
        lines.append(f"{label}: {result['votes']} ({result['percentage']:.1f}%)")
    return "\n".join(lines)
