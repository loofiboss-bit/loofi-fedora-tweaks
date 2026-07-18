"""Geometry and typography tokens shared by every application theme."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class TypographyRoles:
    """Font-family-neutral roles that preserve the desktop system font."""

    page_title_weight: int = 650
    section_title_weight: int = 600
    body_weight: int = 400
    supporting_weight: int = 400
    control_weight: int = 550
    code_family: str = "monospace"


@dataclass(frozen=True)
class DesignTokens:
    """Stable presentation geometry; themes are not allowed to change it."""

    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_6: int = 24
    space_8: int = 32
    radius_control: int = 6
    radius_card: int = 10
    radius_dialog: int = 12
    border_width: int = 1
    focus_width: int = 2
    control_min_height: int = 36
    navigation_row_min_height: int = 44
    content_max_width: int = 1120
    readable_line_length: int = 78
    typography: TypographyRoles = field(default_factory=TypographyRoles)

    def qss_values(self) -> dict[str, str]:
        """Return values formatted for substitution into the structural QSS."""
        values = {
            key: f"{value}px"
            for key, value in asdict(self).items()
            if key != "typography"
        }
        values.update(
            {
                "page_title_weight": str(self.typography.page_title_weight),
                "section_title_weight": str(self.typography.section_title_weight),
                "body_weight": str(self.typography.body_weight),
                "supporting_weight": str(self.typography.supporting_weight),
                "control_weight": str(self.typography.control_weight),
                "code_family": self.typography.code_family,
            }
        )
        return values

    def geometry_signature(self) -> tuple[tuple[str, object], ...]:
        """Return a deterministic signature used to prove theme invariance."""
        values = asdict(self)
        typography = values.pop("typography")
        flattened = {**values, **{f"typography.{key}": value for key, value in typography.items()}}
        return tuple(sorted(flattened.items()))
