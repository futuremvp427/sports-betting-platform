SUPPORTED_SPORTS = {
    "nba": {"enabled": True, "profile": "team_sport"},
    "nfl": {"enabled": True, "profile": "team_sport"},
    "nhl": {"enabled": True, "profile": "team_sport"},
    "soccer": {"enabled": True, "profile": "team_sport"},
    "golf": {"enabled": True, "profile": "player_field"},
    "boxing": {"enabled": True, "profile": "head_to_head"}
}


def get_active_sports():
    return [name for name, meta in SUPPORTED_SPORTS.items() if meta.get("enabled")]


def get_sport_profile(sport):
    return SUPPORTED_SPORTS.get(sport, {})
