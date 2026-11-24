from argparse import ArgumentParser
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from appointments.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Send due appointment reminders once, or poll continuously with --watch."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        interval = getattr(settings, "REMINDER_POLL_SECONDS", 60)
        if interval < 1:
            raise CommandError("REMINDER_POLL_SECONDS must be at least 1.")
        while True:
            send_due_reminders()
            if not options["watch"]:
                return
            close_old_connections()
            sleep(interval)
