import asyncio
from io import BytesIO
from types import SimpleNamespace

from budget_gui_app.ui.pages_data import upload_event_bytes, upload_event_name, upload_event_text


class NewUploadFile:
    name = "example.csv"

    def __init__(self, content: bytes) -> None:
        self._content = content

    async def read(self) -> bytes:
        return self._content

    async def text(self, encoding: str = "utf-8") -> str:
        return self._content.decode(encoding)


def test_new_nicegui_upload_event_uses_file_name_and_async_content() -> None:
    event = SimpleNamespace(file=NewUploadFile(b"date,account\n"))

    assert upload_event_name(event) == "example.csv"
    assert asyncio.run(upload_event_bytes(event)) == b"date,account\n"
    assert asyncio.run(upload_event_text(event)) == "date,account\n"


def test_legacy_nicegui_upload_event_uses_name_and_content_stream() -> None:
    event = SimpleNamespace(name="legacy.json", content=BytesIO(b'{"transactions": []}'))

    assert upload_event_name(event) == "legacy.json"
    assert asyncio.run(upload_event_bytes(event)) == b'{"transactions": []}'

    event = SimpleNamespace(name="legacy.json", content=BytesIO(b'{"transactions": []}'))
    assert asyncio.run(upload_event_text(event)) == '{"transactions": []}'
