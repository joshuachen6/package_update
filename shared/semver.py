from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

SEMVER_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])v?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)(?![A-Za-z0-9_.-])"
)


@total_ordering
@dataclass(frozen=True)
class SemVer:
    raw: str
    major: int
    minor: int
    patch: int
    suffix: str = ""

    @staticmethod
    def parse(value: str) -> SemVer | None:
        if not value:
            return None
        value = str(value).strip()
        value = re.sub(r"^[~^<>=\s]+", "", value)
        match = re.search(
            r"v?(\d+)\.(\d+)\.(\d+)((?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)", value
        )
        if not match:
            return None
        return SemVer(
            raw=f"{match.group(1)}.{match.group(2)}.{match.group(3)}{match.group(4) or ''}",
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            suffix=match.group(4) or "",
        )

    def _pre_release_parts(self) -> tuple:
        if not self.suffix or not self.suffix.startswith("-"):
            return (1,)
        prerelease = self.suffix[1:].split("+")[0]
        parts = []
        for part in prerelease.split("."):
            if part.isdigit():
                parts.append((0, int(part)))
            else:
                parts.append((1, part))
        return (0, tuple(parts))

    def __lt__(self, other: SemVer) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (
            self.major,
            self.minor,
            self.patch,
            self._pre_release_parts(),
        ) < (
            other.major,
            other.minor,
            other.patch,
            other._pre_release_parts(),
        )

    def __str__(self) -> str:
        return self.raw
