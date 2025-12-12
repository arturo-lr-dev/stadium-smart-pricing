"""Unit tests for MatchRepository."""

import pytest
from datetime import datetime, timedelta

from src.domain.repositories.match_repository import MatchRepository
from src.domain.models.match import Match, MatchStatus
from src.domain.models.db_models import MatchDB, MatchStatus as DBMatchStatus
from src.core.exceptions import DatabaseError


class TestMatchRepository:
    """Test suite for MatchRepository."""

    def test_create_match(self, test_db_session, sample_match_data):
        """Test creating a match."""
        repo = MatchRepository(test_db_session)
        match = Match(**sample_match_data)

        created_match = repo.create(match)

        assert created_match.id == sample_match_data["id"]
        assert created_match.home_team == sample_match_data["home_team"]
        assert created_match.away_team == sample_match_data["away_team"]

    def test_get_by_id(self, test_db_session, create_match):
        """Test getting match by ID."""
        repo = MatchRepository(test_db_session)

        match = repo.get_by_id(create_match.id)

        assert match is not None
        assert match.id == create_match.id
        assert match.home_team == create_match.home_team

    def test_get_by_id_not_found(self, test_db_session):
        """Test getting non-existent match."""
        repo = MatchRepository(test_db_session)

        match = repo.get_by_id("non_existent_id")

        assert match is None

    def test_get_all(self, test_db_session, sample_match_data):
        """Test getting all matches."""
        repo = MatchRepository(test_db_session)

        # Create multiple matches
        for i in range(3):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            match = Match(**data)
            repo.create(match)

        matches = repo.get_all()

        assert len(matches) == 3

    def test_update_match(self, test_db_session, create_match):
        """Test updating a match."""
        repo = MatchRepository(test_db_session)

        # Get the match as domain model
        match = repo.get_by_id(create_match.id)
        # Update field
        updated_data = match.model_copy(update={"home_position": 5})

        updated_match = repo.update(create_match.id, updated_data)

        assert updated_match is not None
        assert updated_match.home_position == 5

    def test_delete_match(self, test_db_session, create_match):
        """Test deleting a match."""
        repo = MatchRepository(test_db_session)

        result = repo.delete(create_match.id)

        assert result is True
        assert repo.get_by_id(create_match.id) is None

    def test_exists(self, test_db_session, create_match):
        """Test checking if match exists."""
        repo = MatchRepository(test_db_session)

        assert repo.exists(create_match.id) is True
        assert repo.exists("non_existent_id") is False

    def test_get_upcoming_matches(self, test_db_session, sample_match_data):
        """Test getting upcoming matches."""
        repo = MatchRepository(test_db_session)

        # Create matches at different dates
        now = datetime.now()
        for i in range(5):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["match_date"] = now + timedelta(days=i * 10)
            data["status"] = MatchStatus.SCHEDULED
            match = Match(**data)
            repo.create(match)

        # Get upcoming matches within 30 days
        upcoming = repo.get_upcoming(days=30)

        assert len(upcoming) == 3  # Only 0, 10, 20 days ahead

    def test_get_by_date_range(self, test_db_session, sample_match_data):
        """Test getting matches by date range."""
        repo = MatchRepository(test_db_session)

        # Create matches at different dates
        now = datetime.now()
        for i in range(5):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["match_date"] = now + timedelta(days=i * 10)
            match = Match(**data)
            repo.create(match)

        # Query date range
        start_date = now + timedelta(days=5)
        end_date = now + timedelta(days=25)
        matches = repo.get_by_date_range(start_date, end_date)

        assert len(matches) == 2  # 10 and 20 days ahead

    def test_get_by_competition(self, test_db_session, sample_match_data):
        """Test getting matches by competition."""
        repo = MatchRepository(test_db_session)

        # Create matches with different competitions
        for i, comp in enumerate(["la_liga", "copa_del_rey", "la_liga"]):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["competition"] = comp
            match = Match(**data)
            repo.create(match)

        matches = repo.get_by_competition("la_liga")

        assert len(matches) == 2

    def test_get_by_status(self, test_db_session, sample_match_data):
        """Test getting matches by status."""
        repo = MatchRepository(test_db_session)

        # Create matches with different statuses
        for i, status in enumerate([MatchStatus.SCHEDULED, MatchStatus.ON_SALE, MatchStatus.SCHEDULED]):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["status"] = status
            match = Match(**data)
            repo.create(match)

        matches = repo.get_by_status(MatchStatus.SCHEDULED)

        assert len(matches) == 2

    def test_get_by_team(self, test_db_session, sample_match_data):
        """Test getting matches by team."""
        repo = MatchRepository(test_db_session)

        # Create matches with different teams
        for i in range(3):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            if i == 1:
                data["home_team"] = "Real Madrid"
            match = Match(**data)
            repo.create(match)

        # Get matches involving RCD Mallorca (home or away)
        matches = repo.get_by_team("RCD Mallorca")

        assert len(matches) == 2

    def test_get_by_team_home_only(self, test_db_session, sample_match_data):
        """Test getting home matches only."""
        repo = MatchRepository(test_db_session)

        # Create matches
        for i in range(3):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            if i == 1:
                data["home_team"] = "Real Madrid"
                data["away_team"] = "RCD Mallorca"
            match = Match(**data)
            repo.create(match)

        # Get only home matches
        matches = repo.get_by_team("RCD Mallorca", home_only=True)

        assert len(matches) == 2

    def test_get_derby_matches(self, test_db_session, sample_match_data):
        """Test getting derby matches."""
        repo = MatchRepository(test_db_session)

        # Create matches with derby flag
        for i in range(3):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["is_derby"] = i % 2 == 0  # True for 0 and 2
            match = Match(**data)
            repo.create(match)

        derby_matches = repo.get_derby_matches()

        assert len(derby_matches) == 2

    def test_update_status(self, test_db_session, create_match):
        """Test updating match status."""
        repo = MatchRepository(test_db_session)

        updated = repo.update_status(create_match.id, MatchStatus.ON_SALE)

        assert updated is not None
        assert updated.status == MatchStatus.ON_SALE

    def test_search_matches(self, test_db_session, sample_match_data):
        """Test searching matches with multiple filters."""
        repo = MatchRepository(test_db_session)

        # Create diverse matches
        now = datetime.now()
        for i in range(5):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            data["competition"] = "la_liga" if i < 3 else "copa_del_rey"
            data["status"] = MatchStatus.SCHEDULED if i < 2 else MatchStatus.ON_SALE
            data["match_date"] = now + timedelta(days=i * 10)
            match = Match(**data)
            repo.create(match)

        # Search with filters
        matches = repo.search(
            competition="la_liga",
            status=MatchStatus.SCHEDULED,
            from_date=now,
            to_date=now + timedelta(days=20),
        )

        assert len(matches) == 2

    def test_count(self, test_db_session, sample_match_data):
        """Test counting matches."""
        repo = MatchRepository(test_db_session)

        # Create some matches
        for i in range(5):
            data = sample_match_data.copy()
            data["id"] = f"match_{i}"
            match = Match(**data)
            repo.create(match)

        count = repo.count()

        assert count == 5
