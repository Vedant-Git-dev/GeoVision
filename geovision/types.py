"""Core data types for GeoVision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Location:
    name: str
    lat: float
    lon: float


@dataclass
class DateRange:
    start: str
    end: str

    def __str__(self) -> str:
        return f"{self.start} -> {self.end}"
