"""Read-only country coverage diagnostic. Never print URLs or credentials."""
import json
from datetime import datetime, timezone
from src.config import settings
from src.ticketmaster import _request, _items, TicketmasterError

def main():
    if not settings.ticketmaster_api_key.strip():
        print(json.dumps({"status": "missing_key"}))
        return
    try:
        data = _request("events", {"countryCode": settings.ticketmaster_country_code,
            "classificationName": "music", "startDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sort": "date,asc", "includeTBA": "no", "includeTBD": "no", "size": 20})
        rows = _items(data, "events")
        samples = []
        for e in rows[:3]:
            venues = _items(e, "venues")
            v = venues[0] if venues else {}
            samples.append({"id": e.get("id"), "name": e.get("name"), "start": (e.get("dates") or {}).get("start"),
                "city": (v.get("city") or {}).get("name"), "country": (v.get("country") or {}).get("countryCode")})
        print(json.dumps({"http_status": 200, "country": settings.ticketmaster_country_code,
            "totalElements": data.get("page", {}).get("totalElements"), "sample": samples}, ensure_ascii=False))
    except TicketmasterError as error:
        print(json.dumps({"http_status": error.provider_status, "status": error.code, "message": error.message}, ensure_ascii=False))

if __name__ == "__main__":
    main()
