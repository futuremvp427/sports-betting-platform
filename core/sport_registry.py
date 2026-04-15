SUPPORTED_SPORTS = {
    "nba": {"enabled": True},
    "nfl": {"enabled": True},
    "nhl": {"enabled": True},
    "soccer": {"enabled": True},
    "golf": {"enabled": True}
}

def get_active_sports():
    return [s for s, v in SUPPORTED_SPORTS.items() if v.get("enabled")]
