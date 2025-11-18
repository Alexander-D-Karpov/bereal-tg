import asyncio
import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.utils.markdown import hlink

from bot.storage import Storage


MSK = ZoneInfo("Europe/Moscow")
logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, bot: Bot, storage: Storage):
        self.bot = bot
        self.storage = storage
        self.tasks: dict[str, asyncio.Task] = {}

    def parse_time(self, time_str: str) -> tuple[int, int]:
        hours, minutes = map(int, time_str.split(":"))
        return hours, minutes

    def get_random_time(self, time_from: str, time_to: str, for_date: datetime) -> datetime:
        from_h, from_m = self.parse_time(time_from)
        to_h, to_m = self.parse_time(time_to)

        from_minutes = from_h * 60 + from_m
        to_minutes = to_h * 60 + to_m

        random_minutes = random.randint(from_minutes, to_minutes)
        hours = random_minutes // 60
        minutes = random_minutes % 60

        scheduled_time = for_date.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        logger.debug(
            f"Generated random time: {scheduled_time.strftime('%Y-%m-%d %H:%M')} "
            f"(range: {time_from}-{time_to})"
        )
        return scheduled_time

    def schedule_for_chat(self, chat_id: int) -> None:
        logger.info(f"Scheduling notifications for chat {chat_id}")
        chat_data = self.storage.get_chat_data(chat_id)
        now = datetime.now(MSK)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        last_ping = self.storage.get_last_ping(chat_id)
        pinged_today = last_ping and last_ping.date() == today.date()

        scheduled_today_str = chat_data.get("scheduled_today")
        scheduled_tomorrow_str = chat_data.get("scheduled_tomorrow")

        scheduled_today = self.storage.deserialize_datetime(scheduled_today_str)
        scheduled_tomorrow = self.storage.deserialize_datetime(scheduled_tomorrow_str)

        if not scheduled_today or scheduled_today < now:
            if scheduled_today and scheduled_today < now:
                logger.info(
                    f"Chat {chat_id}: Previous today schedule passed "
                    f"({scheduled_today.strftime('%H:%M')}), generating new one"
                )

            scheduled_today = self.get_random_time(
                chat_data["time_from"], chat_data["time_to"], today
            )

            if scheduled_today < now and pinged_today:
                logger.info(
                    f"Chat {chat_id}: Today's scheduled time {scheduled_today.strftime('%H:%M')} "
                    f"is in the past and already pinged today, skipping"
                )
                scheduled_today = None
            elif scheduled_today < now and not pinged_today:
                logger.info(
                    f"Chat {chat_id}: Today's scheduled time {scheduled_today.strftime('%H:%M')} "
                    f"is in the past but NO ping today yet, keeping it for immediate send"
                )
            else:
                logger.info(
                    f"Chat {chat_id}: Scheduled for today at {scheduled_today.strftime('%H:%M')} MSK"
                )

        if not scheduled_tomorrow or scheduled_tomorrow.date() != tomorrow.date():
            if scheduled_tomorrow:
                logger.info(
                    f"Chat {chat_id}: Previous tomorrow schedule outdated, generating new one"
                )
            scheduled_tomorrow = self.get_random_time(
                chat_data["time_from"], chat_data["time_to"], tomorrow
            )
            logger.info(
                f"Chat {chat_id}: Scheduled for tomorrow at "
                f"{scheduled_tomorrow.strftime('%H:%M')} MSK"
            )

        self.storage.update_chat_data(
            chat_id,
            {
                "scheduled_today": self.storage.serialize_datetime(scheduled_today),
                "scheduled_tomorrow": self.storage.serialize_datetime(scheduled_tomorrow),
            },
        )

        task_key = f"chat_{chat_id}"
        if task_key in self.tasks and not self.tasks[task_key].done():
            logger.info(f"Chat {chat_id}: Cancelling existing task")
            self.tasks[task_key].cancel()

        self.tasks[task_key] = asyncio.create_task(
            self.wait_and_send(chat_id, scheduled_today, scheduled_tomorrow)
        )
        logger.info(f"Chat {chat_id}: Task created and scheduled")

    async def wait_and_send(
        self, chat_id: int, scheduled_today: datetime | None, scheduled_tomorrow: datetime | None
    ) -> None:
        try:
            if scheduled_today:
                wait_seconds = (scheduled_today - datetime.now(MSK)).total_seconds()
                if wait_seconds > 0:
                    logger.info(
                        f"Chat {chat_id}: Waiting {wait_seconds:.0f}s until today's notification "
                        f"({scheduled_today.strftime('%H:%M')} MSK)"
                    )
                    await self.wait_until(scheduled_today)
                else:
                    logger.info(
                        f"Chat {chat_id}: Sending today's notification immediately "
                        f"(scheduled time {scheduled_today.strftime('%H:%M')} already passed)"
                    )
                logger.info(f"Chat {chat_id}: Sending today's notification")
                await self.send_notification(chat_id)

            if scheduled_tomorrow:
                wait_seconds = (scheduled_tomorrow - datetime.now(MSK)).total_seconds()
                logger.info(
                    f"Chat {chat_id}: Waiting {wait_seconds:.0f}s until tomorrow's notification "
                    f"({scheduled_tomorrow.strftime('%H:%M')} MSK)"
                )
                await self.wait_until(scheduled_tomorrow)
                logger.info(f"Chat {chat_id}: Sending tomorrow's notification")
                await self.send_notification(chat_id)

            logger.info(f"Chat {chat_id}: Both notifications sent, rescheduling")
            self.schedule_for_chat(chat_id)
        except asyncio.CancelledError:
            logger.info(f"Chat {chat_id}: Task cancelled")
            raise
        except Exception as e:
            logger.error(f"Chat {chat_id}: Unexpected error in wait_and_send: {e}", exc_info=True)

    async def wait_until(self, target_time: datetime) -> None:
        now = datetime.now(MSK)
        wait_seconds = (target_time - now).total_seconds()
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    async def send_notification(self, chat_id: int) -> None:
        try:
            logger.info(f"Chat {chat_id}: Starting notification send")
            chat_data = self.storage.get_chat_data(chat_id)
            message_text = chat_data.get("message_text", "Пора отправлять свои фотки")

            registered_users = self.storage.get_registered_users(chat_id)

            if not registered_users:
                logger.warning(f"Chat {chat_id}: No registered users, skipping notification")
                return

            logger.info(f"Chat {chat_id}: Found {len(registered_users)} registered users")

            mentions = []
            for user_id_str, user_data in registered_users.items():
                username = user_data.get("username")
                full_name = user_data.get("full_name", "User")

                if username:
                    mentions.append(f"@{username}")
                else:
                    mentions.append(hlink(full_name, f"tg://user?id={user_id_str}"))

            logger.info(f"Chat {chat_id}: Mentioning {len(mentions)} registered users")

            full_message = f"{message_text}\n\n" + " ".join(mentions)

            await self.bot.send_message(chat_id, full_message, parse_mode="HTML")

            ping_time = datetime.now(MSK)
            self.storage.set_last_ping(chat_id, ping_time)
            self.storage.save()

            logger.info(
                f"Chat {chat_id}: Notification sent successfully at "
                f"{ping_time.strftime('%Y-%m-%d %H:%M:%S')} MSK"
            )
        except Exception as e:
            logger.error(
                f"Chat {chat_id}: Failed to send notification: {type(e).__name__}: {e}",
                exc_info=True,
            )

    def reschedule_all(self) -> None:
        logger.info(f"Rescheduling all chats (total: {len(self.storage.data)})")
        for chat_id_str in self.storage.data:
            chat_id = int(chat_id_str)
            try:
                self.schedule_for_chat(chat_id)
            except Exception as e:
                logger.error(f"Chat {chat_id}: Failed to reschedule: {e}", exc_info=True)
        logger.info("Finished rescheduling all chats")

    def stop_all(self) -> None:
        logger.info(f"Stopping all tasks (total: {len(self.tasks)})")
        cancelled_count = 0
        for task_key, task in self.tasks.items():
            if not task.done():
                task.cancel()
                cancelled_count += 1
                logger.debug(f"Cancelled task: {task_key}")
        logger.info(f"Stopped {cancelled_count} active tasks")
