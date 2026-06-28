from typing import Literal

SourceScope = Literal[
    "general_academic",
    "admission",
    "department",
    "unknown",
]
PageKind = Literal[
    "academic",
    "admission",
    "schedule",
    "certificate",
    "contact",
    "unknown",
]
SourceType = Literal["html", "pdf"]
ChunkType = Literal["text", "table"]
