API_PROVIDERS = {
    "odds_api": {"priority": 1, "active": True},
    "espn": {"priority": 2, "active": True}
}

def get_active_apis():
    return sorted([k for k,v in API_PROVIDERS.items() if v["active"]], key=lambda x: API_PROVIDERS[x]["priority"])
