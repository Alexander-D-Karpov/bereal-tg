from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, Message

from bot.scheduler import Scheduler
from bot.storage import Storage


router = Router()


async def setup_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="register", description="Register to receive photo reminders"),
        BotCommand(command="unregister", description="Stop receiving photo reminders"),
        BotCommand(command="who", description="List registered users"),
        BotCommand(command="set_time_from", description="Set start time (MSK) - admin only"),
        BotCommand(command="set_time_to", description="Set end time (MSK) - admin only"),
        BotCommand(command="set_message", description="Set reminder message - admin only"),
        BotCommand(command="get_settings", description="View current chat settings"),
    ]
    await bot.set_my_commands(commands)


@router.message(Command("register"))
async def register_user(message: Message, storage: Storage) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name or message.from_user.first_name

    if storage.is_user_registered(message.chat.id, user_id):
        await message.reply("Вы уже зарегистрированы для получения уведомлений!")
        return

    storage.register_user(message.chat.id, user_id, username, full_name)
    storage.save()

    await message.reply(
        f"{full_name}, вы зарегистрированы! Теперь вы будете получать уведомления BeReal."
    )


@router.message(Command("unregister"))
async def unregister_user(message: Message, storage: Storage) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    user_id = message.from_user.id
    full_name = message.from_user.full_name or message.from_user.first_name

    if storage.unregister_user(message.chat.id, user_id):
        storage.save()
        await message.reply(f"{full_name}, вы удалены из списка получателей уведомлений.")
    else:
        await message.reply("Вы не были зарегистрированы.")


@router.message(Command("who"))
async def list_registered_users(message: Message, storage: Storage) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    registered_users = storage.get_registered_users(message.chat.id)

    if not registered_users:
        await message.reply("Пока никто не зарегистрирован для получения уведомлений.")
        return

    user_list = []
    for _user_id_str, user_data in registered_users.items():
        username = user_data.get("username")
        full_name = user_data.get("full_name", "Unknown")

        if username:
            user_list.append(f"• {full_name} (@{username})")
        else:
            user_list.append(f"• {full_name}")

    response = f"Зарегистрированные пользователи ({len(registered_users)}):\n\n"
    response += "\n".join(user_list)

    await message.reply(response)


@router.message(Command("set_time_from"))
async def set_time_from(
    message: Message, command: CommandObject, storage: Storage, scheduler: Scheduler
) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["creator", "administrator"]:
        await message.reply("Только администраторы могут изменять настройки")
        return

    if not command.args:
        await message.reply("Используйте: /set_time_from HH:MM (например, /set_time_from 09:00)")
        return

    time_str = command.args.strip()
    if not validate_time(time_str):
        await message.reply("Неверный формат времени. Используйте HH:MM")
        return

    chat_data = storage.get_chat_data(message.chat.id)
    time_to = chat_data.get("time_to", "21:00")

    if not validate_time_range(time_str, time_to):
        await message.reply(
            f"Время начала ({time_str}) должно быть раньше времени окончания ({time_to})"
        )
        return

    storage.update_chat_data(message.chat.id, {"scheduled_next": None})
    storage.update_chat_data(message.chat.id, {"time_from": time_str})
    storage.save()

    scheduler.schedule_for_chat(message.chat.id)

    await message.reply(f"Время начала установлено: {time_str} МСК")


@router.message(Command("set_time_to"))
async def set_time_to(
    message: Message, command: CommandObject, storage: Storage, scheduler: Scheduler
) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["creator", "administrator"]:
        await message.reply("Только администраторы могут изменять настройки")
        return

    if not command.args:
        await message.reply("Используйте: /set_time_to HH:MM (например, /set_time_to 21:00)")
        return

    time_str = command.args.strip()
    if not validate_time(time_str):
        await message.reply("Неверный формат времени. Используйте HH:MM")
        return

    chat_data = storage.get_chat_data(message.chat.id)
    time_from = chat_data.get("time_from", "09:00")

    if not validate_time_range(time_from, time_str):
        await message.reply(
            f"Время окончания ({time_str}) должно быть позже времени начала ({time_from})"
        )
        return

    storage.update_chat_data(message.chat.id, {"scheduled_next": None})
    storage.update_chat_data(message.chat.id, {"time_to": time_str})
    storage.save()

    scheduler.schedule_for_chat(message.chat.id)

    await message.reply(f"Время окончания установлено: {time_str} МСК")


@router.message(Command("set_message"))
async def set_message(
    message: Message, command: CommandObject, storage: Storage, scheduler: Scheduler
) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["creator", "administrator"]:
        await message.reply("Только администраторы могут изменять настройки")
        return

    if not command.args:
        await message.reply(
            "Используйте: /set_message [текст]\nНапример: /set_message Время для фото!"
        )
        return

    message_text = command.args.strip()

    if "@" in message_text:
        await message.reply(
            "Текст уведомления не должен содержать упоминания пользователей (@username)"
        )
        return

    if len(message_text) > 200:
        await message.reply("Сообщение слишком длинное (максимум 200 символов)")
        return

    storage.update_chat_data(message.chat.id, {"message_text": message_text})
    storage.save()

    await message.reply(f"Текст уведомления установлен:\n{message_text}")


@router.message(Command("get_settings"))
async def get_settings(message: Message, storage: Storage) -> None:
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("Эта команда работает только в групповых чатах")
        return

    chat_data = storage.get_chat_data(message.chat.id)
    registered_count = len(storage.get_registered_users(message.chat.id))

    settings_text = (
        f"Настройки чата:\n\n"
        f"Время начала: {chat_data['time_from']} МСК\n"
        f"Время окончания: {chat_data['time_to']} МСК\n"
        f"Зарегистрировано пользователей: {registered_count}\n"
        f"Текст уведомления:\n{chat_data.get('message_text', 'Пора отправлять свои фотки')}"
    )

    await message.reply(settings_text)


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    if message.chat.type == "private":
        await message.reply(
            "Привет! Я BeReal бот для групповых чатов.\n\n"
            "Добавь меня в групповой чат, и я буду напоминать участникам "
            "отправлять фотки в случайное время каждый день!\n\n"
            "После добавления в чат, участники должны зарегистрироваться "
            "командой /register чтобы получать уведомления."
        )
    else:
        await message.reply(
            "Привет! Я BeReal бот.\n\n"
            "Чтобы получать уведомления BeReal, "
            "используйте команду /register\n\n"
            "Другие команды:\n"
            "/who - список зарегистрированных\n"
            "/unregister - отписаться от уведомлений\n"
            "/get_settings - настройки чата"
        )


def validate_time(time_str: str) -> bool:
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return False
        hours, minutes = map(int, parts)
        return 0 <= hours <= 23 and 0 <= minutes <= 59
    except ValueError:
        return False


def validate_time_range(time_from: str, time_to: str) -> bool:
    try:
        from_h, from_m = map(int, time_from.split(":"))
        to_h, to_m = map(int, time_to.split(":"))

        from_minutes = from_h * 60 + from_m
        to_minutes = to_h * 60 + to_m

        return from_minutes < to_minutes
    except ValueError:
        return False
