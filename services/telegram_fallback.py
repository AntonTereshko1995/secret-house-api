"""
Direct Telegram notification fallback.
Used when the bot HTTP server is unavailable to ensure admin always gets notified.
"""
import httpx
from db.models.booking import BookingBase
from db.models.tariff import Tariff

_TG_API = "https://api.telegram.org/bot{token}/{method}"

_TARIFF_NAMES = {
    Tariff.HOURS_12: "12 часов",
    Tariff.DAY: "Суточно от 3 человек",
    Tariff.WORKER: "Рабочий",
    Tariff.INCOGNITA_DAY: "Инкогнито (Суточно)",
    Tariff.INCOGNITA_HOURS: "Инкогнито (12 часов)",
    Tariff.INCOGNITA_WORKER: "Инкогнито (Рабочий)",
    Tariff.GIFT: "Подарочный сертификат",
    Tariff.DAY_FOR_COUPLE: "Суточно для двоих",
}


def _yes_no(value: bool) -> str:
    return "Да" if value else "Нет"


def _booking_text(booking: BookingBase, header: str) -> str:
    tariff_name = _TARIFF_NAMES.get(booking.tariff, str(booking.tariff))
    fmt_start = booking.start_date.strftime("%d.%m.%Y %H:%M")
    fmt_end = booking.end_date.strftime("%d.%m.%Y %H:%M")

    user = getattr(booking, "user", None)
    if user:
        contact = (user.user_name or user.contact) if booking.source == "web" else (user.contact or user.user_name)
    else:
        contact = "N/A"

    lines = [
        header,
        "",
        f"Пользователь: {contact or 'N/A'}",
        f"Дата начала: {fmt_start}",
        f"Дата завершения: {fmt_end}",
        f"Тариф: {tariff_name}",
        f"Стоимость: {booking.price} руб.",
        f"Предоплата: {booking.prepayment_price} руб.",
        f"Фотосессия: {_yes_no(booking.has_photoshoot)}",
        f"Сауна: {_yes_no(booking.has_sauna)}",
        f"Белая спальня: {_yes_no(booking.has_white_bedroom)}",
        f"Зеленая спальня: {_yes_no(booking.has_green_bedroom)}",
        f"Секретная комната: {_yes_no(booking.has_secret_room)}",
        f"Количество гостей: {booking.number_of_guests}",
    ]

    if booking.comment:
        lines.append(f"Комментарий: {booking.comment}")
    if booking.wine_preference:
        lines.append(f"Вино: {booking.wine_preference}")
    if booking.transfer_address:
        lines.append(f"Трансфер: {booking.transfer_address}")

    lines.append(f"Источник: {'🌐 Веб' if booking.source == 'web' else '📱 Телеграм'}")

    return "\n".join(lines)


async def _send(token: str, chat_id: str, method: str, **kwargs) -> bool:
    url = _TG_API.format(token=token, method=method)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, **kwargs)
        return r.status_code == 200
    except Exception:
        return False


async def notify_new_booking(token: str, chat_id: str, booking: BookingBase) -> bool:
    """Send a detailed fallback notification about a new web booking (gift cert, no receipt)."""
    text = _booking_text(booking, "⚠️ Новая бронь с сайта (бот был недоступен)")
    return await _send(token, chat_id, "sendMessage",
                       json={"chat_id": chat_id, "text": text})


async def notify_receipt(token: str, chat_id: str, booking: BookingBase,
                         filename: str, content: bytes, content_type: str) -> bool:
    """Forward a receipt file with full booking info directly to admin chat."""
    caption = _booking_text(booking, "⚠️ Чек (бот был недоступен)")
    # Telegram caption limit is 1024 chars
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
    return await _send(token, chat_id, "sendDocument",
                       data={"chat_id": chat_id, "caption": caption},
                       files={"document": (filename, content, content_type)})
