"""
ESPN API provider - fetches game schedules, scores, and team data.
Uses the public ESPN API (no key required).
"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base import BaseProvider
from config import settings
from config.logging_config import get_logger

logger = get_logger("data.espn")

SPORT_PATH_MAP = {
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "ncaab": "basketball/mens-college-basketball",
    "ncaaf": "football/college-football",
}


class ESPNProvider(BaseProvider):
    """Provider for ESPN public API - schedules, scores, team data."""

    def __init__(self):
        self.base_url = settings.espn.base_url

    @property
    def provider_name(self) -> str:
        return "espn"

    def _make_request(self, path: str, params: Dict = None) -> Any:
        """Make a request to the ESPN API."""
        url = f"{self.base_url}/{path}"
        try:
            response = requests.get(url, params=params or {}, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"ESPN API request failed: {e}")
            return self._get_demo_data(path)

    def get_sports(self) -> List[Dict[str, Any]]:
        """Get list of supported sports."""
        return [
            {"key": "nba", "title": "NBA", "path": "basketball/nba"},
            {"key": "nfl", "title": "NFL", "path": "football/nfl"},
            {"key": "mlb", "title": "MLB", "path": "baseball/mlb"},
            {"key": "nhl", "title": "NHL", "path": "hockey/nhl"},
        ]

    def get_events(self, sport: str, dates: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Get events/games for a sport on a given date."""
        sport_path = SPORT_PATH_MAP.get(sport.lower(), sport)
        params = {}
        if dates:
            params["dates"] = dates
        else:
            params["dates"] = datetime.utcnow().strftime("%Y%m%d")

        data = self._make_request(f"{sport_path}/scoreboard", params)
        events = []

        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])

            home = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), {})

            events.append({
                "external_id": event.get("id"),
                "sport": sport,
                "league": sport.upper(),
                "home_team_name": home.get("team", {}).get("displayName", "Unknown"),
                "away_team_name": away.get("team", {}).get("displayName", "Unknown"),
                "home_team_abbr": home.get("team", {}).get("abbreviation"),
                "away_team_abbr": away.get("team", {}).get("abbreviation"),
                "scheduled_time": event.get("date"),
                "status": self._map_status(event.get("status", {}).get("type", {}).get("name", "")),
                "home_score": int(home.get("score", 0)) if home.get("score") else None,
                "away_score": int(away.get("score", 0)) if away.get("score") else None,
                "venue": competition.get("venue", {}).get("fullName"),
                "season": event.get("season", {}).get("year"),
                "source": self.provider_name,
            })

        logger.info(f"Fetched {len(events)} events for {sport}")
        return events

    def get_odds(self, sport: str, **kwargs) -> List[Dict[str, Any]]:
        """ESPN doesn't provide odds directly; return empty list."""
        logger.info("ESPN does not provide odds data. Use OddsAPIProvider instead.")
        return []

    def get_historical_scores(self, sport: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Fetch historical game results for a date range.
        Iterates day by day through the range.
        """
        sport_path = SPORT_PATH_MAP.get(sport.lower(), sport)
        all_events = []

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start

        while current <= end:
            date_str = current.strftime("%Y%m%d")
            try:
                data = self._make_request(f"{sport_path}/scoreboard", {"dates": date_str})
                for event in data.get("events", []):
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})

                    status_name = event.get("status", {}).get("type", {}).get("name", "")
                    if status_name not in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                        current += timedelta(days=1)
                        continue

                    home_score = int(home.get("score", 0)) if home.get("score") else 0
                    away_score = int(away.get("score", 0)) if away.get("score") else 0

                    all_events.append({
                        "external_id": event.get("id"),
                        "sport": sport,
                        "league": sport.upper(),
                        "home_team_name": home.get("team", {}).get("displayName", "Unknown"),
                        "away_team_name": away.get("team", {}).get("displayName", "Unknown"),
                        "scheduled_time": event.get("date"),
                        "status": "final",
                        "home_score": home_score,
                        "away_score": away_score,
                        "winner": (
                            home.get("team", {}).get("displayName")
                            if home_score > away_score
                            else away.get("team", {}).get("displayName")
                        ),
                        "venue": competition.get("venue", {}).get("fullName"),
                        "season": event.get("season", {}).get("year"),
                        "source": self.provider_name,
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch data for {date_str}: {e}")

            current += timedelta(days=1)

        logger.info(f"Fetched {len(all_events)} historical events for {sport}")
        return all_events

    def get_teams(self, sport: str) -> List[Dict[str, Any]]:
        """Get all teams for a sport."""
        sport_path = SPORT_PATH_MAP.get(sport.lower(), sport)
        data = self._make_request(f"{sport_path}/teams")
        teams = []

        for team_entry in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = team_entry.get("team", {})
            teams.append({
                "name": team.get("displayName"),
                "abbreviation": team.get("abbreviation"),
                "external_id": team.get("id"),
                "sport": sport,
                "league": sport.upper(),
                "logo": team.get("logos", [{}])[0].get("href") if team.get("logos") else None,
            })

        return teams

    @staticmethod
    def _map_status(espn_status: str) -> str:
        """Map ESPN status to internal status."""
        status_map = {
            "STATUS_SCHEDULED": "scheduled",
            "STATUS_IN_PROGRESS": "in_progress",
            "STATUS_HALFTIME": "in_progress",
            "STATUS_FINAL": "final",
            "STATUS_FULL_TIME": "final",
            "STATUS_POSTPONED": "postponed",
            "STATUS_CANCELED": "canceled",
        }
        return status_map.get(espn_status, "unknown")

    def _get_demo_data(self, path: str) -> Dict[str, Any]:
        """Return demo data when API is unavailable."""
        now = datetime.utcnow().isoformat()
        return {
            "events": [
                {
                    "id": "demo_espn_001",
                    "date": now,
                    "status": {"type": {"name": "STATUS_SCHEDULED"}},
                    "season": {"year": 2025},
                    "competitions": [
                        {
                            "venue": {"fullName": "Crypto.com Arena"},
                            "competitors": [
                                {
                                    "homeAway": "home",
                                    "score": "0",
                                    "team": {
                                        "displayName": "Los Angeles Lakers",
                                        "abbreviation": "LAL",
                                        "id": "13",
                                    },
                                },
                                {
                                    "homeAway": "away",
                                    "score": "0",
                                    "team": {
                                        "displayName": "Boston Celtics",
                                        "abbreviation": "BOS",
                                        "id": "2",
                                    },
                                },
                            ],
                        }
                    ],
                }
            ]
        }
