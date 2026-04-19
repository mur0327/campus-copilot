"""Thermal printer service for the Raspberry Pi kiosk."""

from collections.abc import Sequence

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Campus Copilot Print Service")


class PrintSource(BaseModel):
    title: str
    url: str | None = None


class PrintRequest(BaseModel):
    question: str = ""
    answer: str = ""
    sources: Sequence[PrintSource] = Field(default_factory=list)
    qr_url: str = ""


@app.post("/print")
def print_receipt(payload: PrintRequest) -> dict[str, str]:
    try:
        from escpos.printer import Usb  # type: ignore

        printer = Usb(0x04B8, 0x0202)
        printer.set(align="center", bold=True)
        printer.text("Campus Copilot\n")
        printer.set(align="left", bold=False)
        printer.text(f"\n[질문]\n{payload.question}\n")
        printer.text(f"\n[답변]\n{payload.answer}\n")

        if payload.sources:
            printer.text("\n[출처]\n")
            for source in payload.sources:
                printer.text(f" - {source.title}\n")

        if payload.qr_url:
            printer.qr(payload.qr_url, size=6)

        printer.cut()
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
