"""
Application version information.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:

    major: int

    minor: int

    patch: int

    stage: str = "stable"

    def __str__(self) -> str:
        return (
            f"{self.major}."
            f"{self.minor}."
            f"{self.patch}-"
            f"{self.stage}"
        )


APP_VERSION = Version(
    major=1,
    minor=0,
    patch=0,
)

VERSION = str(APP_VERSION)