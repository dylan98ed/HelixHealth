"""Local SMTP inbox that can reject DATA or lose the acceptance reply in tests."""

import json
import socket
import sys
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from pathlib import Path
from tempfile import gettempdir
from threading import Event
from uuid import uuid4

from aiosmtpd.controller import Controller

LOST_REPLY_ADDRESS = "20000019@acceptance.example.test"


class Inbox:
    def __init__(self, directory, *, lost_reply_address=LOST_REPLY_ADDRESS):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lost_reply_address = lost_reply_address
        self.refuse_once = set()

    async def handle_DATA(self, server, session, envelope):
        (recipient,) = envelope.rcpt_tos
        if recipient in self.refuse_once:
            self.refuse_once.remove(recipient)
            return "451 Temporary test rejection"
        target = self.directory / f"{uuid4()}.eml"
        pending = target.with_suffix(".tmp")
        pending.write_bytes(envelope.original_content)
        pending.replace(target)
        if recipient == self.lost_reply_address:
            server.transport.close()
        return "250 Received"

    def messages(self):
        messages = []
        for path in sorted(self.directory.glob("*.eml")):
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            messages.append(
                dict(
                    to=str(message["To"]),
                    message_id=str(message["Message-ID"]),
                    body=message.get_content(),
                )
            )
        return messages


@contextmanager
def local_mailbox(directory):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    inbox = Inbox(directory)
    controller = Controller(inbox, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield port, inbox
    finally:
        controller.stop()


if __name__ == "__main__":
    inbox = Inbox(Path(gettempdir()) / "reminder-test-inbox")
    if "--read" in sys.argv:
        print(json.dumps(inbox.messages()))
    else:
        controller = Controller(inbox, hostname="0.0.0.0", port=1025)
        controller.start()
        try:
            Event().wait()
        finally:
            controller.stop()
