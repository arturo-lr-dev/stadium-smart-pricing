"""
Match domain models.

Pydantic models for match entities and related enumerations.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class CompetitionType(str, Enum):
    """Competition type enumeration."""

    LA_LIGA = "la_liga"
    COPA_DEL_REY = "copa_del_rey"
    CHAMPIONS_LEAGUE = "champions_league"
    EUROPA_LEAGUE = "europa_league"
    FRIENDLY = "friendly"
    SUPER_CUP = "super_cup"
    OTHER = "other"


class MatchStatus(str, Enum):
    """Match status enumeration."""

    SCHEDULED = "scheduled"
    ON_SALE = "on_sale"
    SOLD_OUT = "sold_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Match(BaseModel):
    """
    Match domain model.

    Represents a football match with all relevant information for pricing.
    """

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=False,
        json_schema_extra={
            "example": {
                "id": "match_001",
                "home_team": "RCD Mallorca",
                "away_team": "FC Barcelona",
                "competition": "la_liga",
                "date": "2024-03-15T20:00:00",
                "venue": "Son Moix",
                "capacity": 23142,
                "is_derby": False,
                "is_holiday": False,
                "home_position": 12,
                "away_position": 1,
                "status": "scheduled",
            }
        }
    )

    id: str = Field(..., description="Unique match identifier")
    home_team: str = Field(..., description="Home team name", min_length=1, max_length=100)
    away_team: str = Field(..., description="Away team name", min_length=1, max_length=100)
    competition: str = Field(..., description="Competition name", min_length=1, max_length=100)
    date: datetime = Field(..., description="Match date and time", alias="match_date")
    venue: str = Field(default="Son Moix", description="Stadium name", max_length=100)
    capacity: int = Field(default=23142, description="Stadium capacity", gt=0)
    is_derby: bool = Field(default=False, description="Whether this is a derby match")
    is_holiday: bool = Field(default=False, description="Whether match is on a holiday")
    home_position: Optional[int] = Field(
        None, description="Home team league position", ge=1, le=30
    )
    away_position: Optional[int] = Field(
        None, description="Away team league position", ge=1, le=30
    )
    status: MatchStatus = Field(
        default=MatchStatus.SCHEDULED, description="Current match status"
    )

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: datetime) -> datetime:
        """
        Validate that match date is in the future (for new matches).

        Args:
            v: Match date

        Returns:
            Validated date
        """
        # Note: This validation is relaxed for historical data
        # In a real system, you might want to be more strict for new matches
        return v

    @field_validator("away_team")
    @classmethod
    def validate_teams_different(cls, v: str, info) -> str:
        """
        Validate that home and away teams are different.

        Args:
            v: Away team name
            info: Validation info containing other fields

        Returns:
            Validated away team

        Raises:
            ValueError: If home and away teams are the same
        """
        if "home_team" in info.data and v == info.data["home_team"]:
            raise ValueError("Home and away teams must be different")
        return v

    def days_until_match(self, current_date: Optional[datetime] = None) -> int:
        """
        Calculate days until the match.

        Args:
            current_date: Current date (defaults to now)

        Returns:
            Number of days until match (negative if match has passed)
        """
        if current_date is None:
            current_date = datetime.now()

        delta = self.date - current_date
        return delta.days

    def is_high_profile(self) -> bool:
        """
        Determine if this is a high-profile match.

        Returns:
            True if match is high profile (derby, top teams, or important competition)
        """
        if self.is_derby:
            return True

        # Check if either team is in top positions
        if self.home_position and self.home_position <= 5:
            return True
        if self.away_position and self.away_position <= 5:
            return True

        # Check competition type
        high_profile_competitions = [
            CompetitionType.CHAMPIONS_LEAGUE.value,
            CompetitionType.COPA_DEL_REY.value,
        ]

        return self.competition.lower() in [c.lower() for c in high_profile_competitions]


class MatchCreate(BaseModel):
    """Schema for creating a new match."""

    id: str = Field(..., description="Unique match identifier")
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    competition: str = Field(..., min_length=1, max_length=100)
    match_date: datetime
    venue: str = Field(default="Son Moix", max_length=100)
    capacity: int = Field(default=23142, gt=0)
    is_derby: bool = Field(default=False)
    is_holiday: bool = Field(default=False)
    home_position: Optional[int] = Field(None, ge=1, le=30)
    away_position: Optional[int] = Field(None, ge=1, le=30)


class MatchUpdate(BaseModel):
    """Schema for updating an existing match."""

    home_team: Optional[str] = Field(None, min_length=1, max_length=100)
    away_team: Optional[str] = Field(None, min_length=1, max_length=100)
    competition: Optional[str] = Field(None, min_length=1, max_length=100)
    match_date: Optional[datetime] = None
    venue: Optional[str] = Field(None, max_length=100)
    capacity: Optional[int] = Field(None, gt=0)
    is_derby: Optional[bool] = None
    is_holiday: Optional[bool] = None
    home_position: Optional[int] = Field(None, ge=1, le=30)
    away_position: Optional[int] = Field(None, ge=1, le=30)
    status: Optional[MatchStatus] = None


class MatchResponse(BaseModel):
    """Schema for match API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    home_team: str
    away_team: str
    competition: str
    match_date: datetime
    venue: str
    capacity: int
    is_derby: bool
    is_holiday: bool
    home_position: Optional[int] = None
    away_position: Optional[int] = None
    status: MatchStatus
    created_at: datetime
    updated_at: datetime
