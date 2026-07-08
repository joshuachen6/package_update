from __future__ import annotations

import re
from dataclasses import dataclass

MAVEN_VERSION_RE = re.compile(
    r"(?<![A-Za-z0-9_@/.-])"
    r"(\d+\.\d+(?:\.\d+)*(?:[._-][A-Za-z0-9][A-Za-z0-9._-]*)?)"
    r"(?![A-Za-z0-9_@/])"
)


@dataclass(frozen=True)
class MavenVersion:
    """
    Comparable Maven version that handles common qualifiers.
    Comparison is on (major, minor, patch, build) only; qualifier is ignored
    so 5.3.27.RELEASE and 5.3.27 are treated as equal rank.
    """

    raw: str
    major: int
    minor: int
    patch: int
    build: int = 0

    _PATTERN = re.compile(
        r"^(\d+)\.(\d+)(?:\.(\d+)(?:\.(\d+))?)?(?:[.\-][A-Za-z0-9][A-Za-z0-9._-]*)?$"
    )

    @staticmethod
    def parse(v_str: str) -> MavenVersion | None:
        v_str = (v_str or "").strip()
        m = MavenVersion._PATTERN.match(v_str)
        if not m:
            return None
        return MavenVersion(
            raw=v_str,
            major=int(m.group(1)),
            minor=int(m.group(2)),
            patch=int(m.group(3) or 0),
            build=int(m.group(4) or 0),
        )

    def _key(self) -> tuple[int, int, int, int]:
        return (self.major, self.minor, self.patch, self.build)

    def __lt__(self, other: MavenVersion) -> bool:
        return self._key() < other._key()

    def __le__(self, other: MavenVersion) -> bool:
        return self._key() <= other._key()

    def __gt__(self, other: MavenVersion) -> bool:
        return self._key() > other._key()

    def __ge__(self, other: MavenVersion) -> bool:
        return self._key() >= other._key()

    def __str__(self) -> str:
        return self.raw
