"""Unified Telegram notification service.

All notifications are routed through the bot's HTTP server.
Routers should only call the `on_*` methods.
"""

import logging

import httpx
from db.models.booking import BookingBase
from db.models.gift import GiftBase
from db.models.tariff import Tariff

_log = logging.getLogger(__name__)

_TARIFF_NAMES: dict[Tariff, str] = {
    Tariff.HOURS_12: "12 часов",
    Tariff.DAY: "Суточно от 3 человек",
    Tariff.WORKER: "Рабочий",
    Tariff.INCOGNITA_DAY: "Инкогнито (Суточно)",
    Tariff.INCOGNITA_HOURS: "Инкогнито (12 часов)",
    Tariff.INCOGNITA_WORKER: "Инкогнито (Рабочий)",
    Tariff.GIFT: "Подарочный сертификат",
    Tariff.DAY_FOR_COUPLE: "Суточно для двоих",
}


_WINE_NAMES: dict[str, str] = {
    "none": "Не нужно вино",
    "white-sweet": "Белое сладкое",
    "white-semi-sweet": "Белое полусладкое",
    "white-dry": "Белое сухое",
    "white-semi-dry": "Белое полусухое",
    "red-sweet": "Красное сладкое",
    "red-semi-sweet": "Красное полусладкое",
    "red-dry": "Красное сухое",
    "red-semi-dry": "Красное полусухое",
}


def _tariff_name(tariff: Tariff) -> str:
    return _TARIFF_NAMES.get(tariff, str(tariff))


def _wine_name(wine_id: str) -> str:
    return _WINE_NAMES.get(wine_id, wine_id)


def _active_services_lines(
    *,
    has_photoshoot: bool,
    has_sauna: bool,
    has_bath_tub: bool,
    has_extra_bedroom: bool,
    has_secret_room: bool,
    wine: str | None,
    transfer_address: str | None,
) -> list[str]:
    lines = []
    if has_photoshoot:
        lines.append("Фотосессия: Да")
    if has_sauna:
        lines.append("Сауна: Да")
    if has_bath_tub:
        lines.append("Горячий чан: Да")
    if has_extra_bedroom:
        lines.append("Доп. спальня: Да")
    if has_secret_room:
        lines.append("Секретная комната: Да")
    if wine:
        lines.append(f"Вино: {wine}")
    if transfer_address:
        lines.append(f"Трансфер: {transfer_address}")
    return lines


def _yes_no(value: bool) -> str:
    return "Да" if value else "Нет"


def _contact_from_booking(booking: BookingBase) -> str:
    user = getattr(booking, "user", None)
    if not user:
        return "N/A"
    contact = (
        (user.user_name or user.contact)
        if booking.source == "web"
        else (user.contact or user.user_name)
    )
    return contact or "N/A"


def _booking_text(booking: BookingBase, header: str) -> str:
    tariff_name = _tariff_name(booking.tariff)
    lines = [
        header,
        "",
        f"Пользователь: {_contact_from_booking(booking)}",
        f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}",
        f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}",
        f"Тариф: {tariff_name}",
        f"Стоимость: {booking.price} руб.",
        f"Предоплата: {booking.prepayment_price} руб.",
        f"Фотосессия: {_yes_no(booking.has_photoshoot)}",
        f"Сауна: {_yes_no(booking.has_sauna)}",
        f"Горячий чан: {_yes_no(booking.has_bath_tub)}",
        f"Белая спальня: {_yes_no(booking.has_white_bedroom)}",
        f"Зеленая спальня: {_yes_no(booking.has_green_bedroom)}",
        f"Секретная комната: {_yes_no(booking.has_secret_room)}",
        f"Количество гостей: {booking.number_of_guests}",
    ]
    if booking.comment:
        lines.append(f"Комментарий: {booking.comment}")
    if booking.wine_preference:
        wine_names = ", ".join(
            _wine_name(w.strip()) for w in booking.wine_preference.split(",") if w.strip()
        )
        lines.append(f"Вино: {wine_names}")
    if booking.transfer_address:
        lines.append(f"Трансфер: {booking.transfer_address}")
    lines.append(f"Источник: {'🌐 Веб' if booking.source == 'web' else '📱 Телеграм'}")
    return "\n".join(lines)


class TelegramService:
    """Single point of contact for all Telegram notifications.

    Instantiate once at startup via ``get_telegram_service`` and inject
    with FastAPI ``Depends``.  Routers call ``on_*`` methods only.
    """

    def __init__(self, *, bot_base_url: str) -> None:
        self._bot_base_url = bot_base_url.rstrip("/") if bot_base_url else ""

    # ------------------------------------------------------------------
    # Public interface — called by routers
    # ------------------------------------------------------------------

    @staticmethod
    def tariff_display_name(tariff: Tariff | None) -> str:
        return "N/A" if tariff is None else _tariff_name(tariff)

    async def on_new_booking(
        self,
        booking_id: int,
        booking: BookingBase,
        *,
        no_receipt_expected: bool,
    ) -> None:
        """Notify admin about a new web booking (only when no receipt is expected)."""
        if not no_receipt_expected:
            return

        if self._bot_base_url:
            ok = await self._post_to_bot(
                f"{self._bot_base_url}/api/new-booking",
                json={"booking_id": booking_id},
                timeout=5,
            )
            if not ok:
                _log.warning("on_new_booking: bot unavailable, booking_id=%s", booking_id)

    async def on_receipt_uploaded(
        self,
        booking: BookingBase,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str | None:
        """Forward a payment receipt to the admin chat via bot.

        Returns Telegram ``file_id`` when the bot returned one; otherwise ``None``.
        """
        if self._bot_base_url:
            r = await self._request_bot(
                f"{self._bot_base_url}/api/receipt",
                data={"booking_id": str(booking.id)},
                files={"file": (filename, content, content_type)},
            )
            if r is not None:
                if r.status_code == 200:
                    return r.json().get("file_id")
                _log.warning(
                    "on_receipt_uploaded: bot returned status=%s body=%s",
                    r.status_code,
                    r.text[:200],
                )
        return None

    async def on_booking_cancelled(self, booking: BookingBase) -> None:
        await self._notify_inform(
            f"Отмена бронирования!\n"
            f"Контакт клиента: {_contact_from_booking(booking)}\n"
            f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}\n"
        )

    async def on_tariff_changed(
        self,
        booking: BookingBase,
        old_tariff_name: str,
        new_tariff_name: str,
        contact: str,
        new_price: float,
    ) -> None:
        wine = None
        if booking.wine_preference:
            wine = ", ".join(
                _wine_name(w.strip()) for w in booking.wine_preference.split(",") if w.strip()
            )
        lines = [
            "Изменение тарифа бронирования!",
            f"Контакт клиента: {contact}",
            f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}",
            f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}",
            f"Старый тариф: {old_tariff_name}",
            f"Новый тариф: {new_tariff_name}",
            f"Новая стоимость: {new_price} руб.",
        ]
        lines += _active_services_lines(
            has_photoshoot=booking.has_photoshoot,
            has_sauna=booking.has_sauna,
            has_bath_tub=booking.has_bath_tub,
            has_extra_bedroom=booking.has_white_bedroom or booking.has_green_bedroom,
            has_secret_room=booking.has_secret_room,
            wine=wine,
            transfer_address=booking.transfer_address,
        )
        await self._notify_inform("\n".join(lines))

    async def on_services_changed(
        self,
        booking: BookingBase,
        *,
        has_photoshoot: bool,
        has_sauna: bool,
        has_bath_tub: bool,
        has_extra_bedroom: bool,
        has_secret_room: bool,
        wine_selection: list,
        needs_transfer: bool,
        transfer_address: str | None,
        new_price: float,
        contact: str,
    ) -> None:
        wine = ", ".join(_wine_name(w) for w in wine_selection) if wine_selection else None
        lines = [
            "Изменение услуг бронирования!",
            f"Контакт клиента: {contact}",
            f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}",
            f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}",
            f"Тариф: {_tariff_name(booking.tariff)}",
            f"Новая стоимость: {new_price} руб.",
        ]
        lines += _active_services_lines(
            has_photoshoot=has_photoshoot,
            has_sauna=has_sauna,
            has_bath_tub=has_bath_tub,
            has_extra_bedroom=has_extra_bedroom,
            has_secret_room=has_secret_room,
            wine=wine,
            transfer_address=transfer_address if needs_transfer else None,
        )
        await self._notify_inform("\n".join(lines))

    async def on_booking_confirmed(self, booking: BookingBase) -> None:
        await self._notify_inform(
            f"Оплата подтверждена администратором!\n"
            f"Контакт клиента: {_contact_from_booking(booking)}\n"
            f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"Тариф: {_tariff_name(booking.tariff)}\n"
            f"Стоимость: {booking.price} руб.\n"
        )

    async def on_price_changed(
        self,
        booking: BookingBase,
        *,
        old_price: float,
        new_price: float,
        old_prepayment: float,
        new_prepayment: float,
        contact: str,
    ) -> None:
        lines = [
            "Изменение стоимости бронирования!",
            f"Контакт клиента: {contact}",
            f"Дата начала: {booking.start_date.strftime('%d.%m.%Y %H:%M')}",
            f"Дата завершения: {booking.end_date.strftime('%d.%m.%Y %H:%M')}",
        ]
        if old_price != new_price:
            lines.append(f"Старая стоимость: {old_price} руб.")
            lines.append(f"Новая стоимость: {new_price} руб.")
        if old_prepayment != new_prepayment:
            lines.append(f"Старая предоплата: {old_prepayment} руб.")
            lines.append(f"Новая предоплата: {new_prepayment} руб.")
        await self._notify_inform("\n".join(lines))

    async def on_rescheduled(
        self,
        *,
        old_start,
        old_end,
        new_start,
        new_end,
        contact: str,
    ) -> None:
        await self._notify_inform(
            f"Перенос даты бронирования!\n"
            f"Контакт клиента: {contact}\n"
            f"Старая дата начала: {old_start.strftime('%d.%m.%Y %H:%M')}\n"
            f"Старая дата завершения: {old_end.strftime('%d.%m.%Y %H:%M')}\n"
            f"Новая дата начала: {new_start.strftime('%d.%m.%Y %H:%M')}\n"
            f"Новая дата завершения: {new_end.strftime('%d.%m.%Y %H:%M')}\n"
        )

    async def on_gift_purchased(
        self,
        gift_id: int,
        gift: GiftBase,
        filename: str | None,
        content: bytes | None,
        content_type: str | None,
    ) -> None:
        """Notify admin about a new gift certificate purchase via bot."""
        if self._bot_base_url:
            ok = await self._send_gift_to_bot(gift_id, filename, content, content_type)
            if not ok:
                _log.warning("on_gift_purchased: bot unavailable, gift_id=%s", gift_id)

    # ------------------------------------------------------------------
    # Low-level: bot HTTP server
    # ------------------------------------------------------------------

    async def _request_bot(
        self, url: str, *, timeout: float = 30, **kwargs
    ) -> httpx.Response | None:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(url, **kwargs)
        except Exception as e:
            _log.warning("bot unavailable url=%s: %s", url, e)
            return None

    async def _post_to_bot(self, url: str, *, timeout: float = 30, **kwargs) -> bool:
        r = await self._request_bot(url, timeout=timeout, **kwargs)
        return r is not None and r.status_code == 200

    async def _send_gift_to_bot(
        self,
        gift_id: int,
        filename: str | None,
        content: bytes | None,
        content_type: str | None,
    ) -> bool:
        files_dict = (
            {"file": (filename or "receipt", content, content_type)}
            if (content and content_type)
            else {}
        )
        return await self._post_to_bot(
            f"{self._bot_base_url}/api/gifts/notify",
            data={"gift_id": str(gift_id)},
            files=files_dict if files_dict else None,
        )

    async def _notify_inform(self, text: str) -> None:
        if not self._bot_base_url:
            return
        ok = await self._post_to_bot(
            f"{self._bot_base_url}/api/notify/inform",
            json={"text": text},
            timeout=5,
        )
        if not ok:
            _log.warning("_notify_inform: bot unavailable, message lost")
