from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Beat(BaseModel):
    summary: str = Field(min_length=10)
    word_target: int | None = Field(default=None, gt=0)


class Chapter(BaseModel):
    number: int = Field(gt=0)
    title: str = Field(min_length=1)
    synopsis: str = Field(min_length=20)
    beats: list[Beat] = Field(min_length=2, max_length=12)
    code_examples: list[str] = Field(default_factory=list, max_length=20)
    tables: list[str] = Field(default_factory=list, max_length=10)
    diagrams: list[str] = Field(default_factory=list, max_length=10)
    charts: list[str] = Field(default_factory=list, max_length=10)
    images: list[str] = Field(default_factory=list, max_length=4)
    word_target: int = Field(gt=0)


class Outline(BaseModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str = "epubgen"
    topic: str
    style: str
    chapters: list[Chapter] = Field(min_length=3, max_length=40)


class RefinedTopic(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    subtitle: str = Field(min_length=5, max_length=120)
    angle: str = Field(min_length=10, max_length=160)


class TopicSuggestions(BaseModel):
    suggestions: list[RefinedTopic] = Field(min_length=3, max_length=3)


class Options(BaseModel):
    topic: str
    style: str = "oreilly"
    out: Path
    workdir: Path | None = None
    chapters: int | None = None
    words: int = 3000
    model: str = "claude-opus-4-7"
    concurrency: int = 3
    kindle: bool = False
    no_cover: bool = False
    no_diagrams: bool = False
    no_images: bool = False
    cover_prompt: str | None = None
    author: str = "epubgen"
    preferred_title: str | None = None
    preferred_subtitle: str | None = None
    description: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    force: bool = False
    dry_run: bool = False
    verbose: bool = False

    def freeze_dict(self) -> dict[str, Any]:
        # Subset that defines reproducibility; excludes IO paths and runtime flags.
        return {
            "topic": self.topic,
            "style": self.style,
            "chapters": self.chapters,
            "words": self.words,
            "model": self.model,
            "kindle": self.kindle,
            "author": self.author,
            "preferred_title": self.preferred_title,
            "preferred_subtitle": self.preferred_subtitle,
            "description": self.description,
        }
