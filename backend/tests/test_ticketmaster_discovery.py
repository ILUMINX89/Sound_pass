import unittest
from unittest.mock import patch

from src import ticketmaster as tm
from src import seatgeek
from src.artist_origins import CURATED, ArtistOrigin


DUKI_ID = "K8vZ917bvf7"
OUTSIDE_ID = "artist-outside"
UNKNOWN_ID = "artist-unknown"
CATALOG = {
    **CURATED,
    OUTSIDE_ID: ArtistOrigin("Outside", frozenset({"GB"}), "https://example.test/identity"),
}


def event(event_id, artist_id, venue_country, **fields):
    return {
        "id": event_id,
        "name": "Example concert",
        "dates": {"start": {"localDate": "2099-01-01"}},
        "_embedded": {
            "attractions": [{"id": artist_id}],
            "venues": [{"name": "Venue", "country": {"countryCode": venue_country, "name": venue_country}}],
        },
        **fields,
    }


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        tm._cache.clear()
        self.addCleanup(tm._cache.clear)
        config = patch.multiple(tm.settings, ticketmaster_api_key="test", ticketmaster_artist_origins="US,MX,CO,AR,PR")
        config.start()
        self.addCleanup(config.stop)

    def test_catalog_pages_by_stable_identity_and_ignores_venue_country(self):
        calls = []

        def request(resource, params):
            calls.append((resource, params))
            page = params["page"]
            items = [event("outside", OUTSIDE_ID, "MX"), event("unknown", UNKNOWN_ID, "MX")]
            if page == 1:
                items = [event("duki-in-es", DUKI_ID, "ES")]
            return {"page": {"totalPages": 2}, "_embedded": {"events": items}}

        with patch.object(tm, "_request", side_effect=request):
            cards = tm.get_public_concerts("Duki", CATALOG)
            upcoming = tm.get_artist_upcoming_events("Duki", CATALOG, artist_id=DUKI_ID)
        self.assertEqual([card["id"] for card in cards], ["duki-in-es"])
        self.assertEqual(cards[0]["venue"]["country_code"], "ES")
        self.assertEqual(cards[0]["artist_origins"], ["AR"])
        self.assertEqual([row["id"] for row in upcoming["events"]], ["duki-in-es"])
        self.assertEqual(upcoming["events"][0]["country"], "ES")
        self.assertEqual({params["page"] for _, params in calls}, {0, 1})
        self.assertTrue(all(params["attractionId"] == DUKI_ID and "countryCode" not in params for _, params in calls))

    def test_unknown_outside_and_ambiguous_artist_never_query_dates(self):
        cases = [
            ([UNKNOWN_ID], "no_events", "no está verificado"),
            ([OUTSIDE_ID], "no_events", "fuera del catálogo"),
            ([DUKI_ID, UNKNOWN_ID], "ambiguous", "mismo nombre"),
        ]
        for ids, status, message in cases:
            with self.subTest(ids=ids), patch.object(tm, "_request") as request:
                tm._cache.clear()
                request.return_value = {"_embedded": {"attractions": [{"id": value, "name": "Duki"} for value in ids]}}
                result = tm.get_artist_upcoming_events("Duki", CATALOG)
                self.assertEqual(result["status"], status)
                self.assertIn(message, result["message"])
                self.assertEqual(result["events"], [])
                self.assertEqual(request.call_count, 1)
                self.assertEqual(request.call_args.args[0], "attractions")

    def test_detail_preserves_prices_and_only_accepts_official_map(self):
        complete = event(
            "123", DUKI_ID, "ES",
            priceRanges=[{"min": 49, "max": 120.5, "currency": "EUR"},
                         {"min": 10, "max": 10, "currency": "USD"}],
            seatmap={"staticUrl": "https://media.ticketmaster.eu/maps/seat.png"},
        )
        missing = event("event-2", DUKI_ID, "ES", seatmap={"staticUrl": "https://media.ticketmaster.eu.example.test/seat.png"})
        with patch.object(tm, "_request", side_effect=[complete, missing]) as request:
            card, _ = tm.get_event_detail("123", CATALOG)
            unavailable, _ = tm.get_event_detail("event-2", CATALOG)
        self.assertEqual(request.call_args_list[0].args[0], "events/123")
        self.assertEqual(card["price_ranges"], [{"min": 49, "max": 120.5, "currency": "EUR"},
                                               {"min": 10, "max": 10, "currency": "USD"}])
        self.assertEqual(card["seatmap_url"], "https://media.ticketmaster.eu/maps/seat.png")
        self.assertNotIn("ticket_types", card)
        self.assertIsNone(unavailable["price_ranges"])
        self.assertIsNone(unavailable["seatmap_url"])


class PriceFallbackTest(unittest.TestCase):
    def test_only_an_exact_unambiguous_show_can_supply_price(self):
        card = {"artist": "Duki", "event_date": "2099-01-01", "event_time": "19:00:00",
                "venue": {"name": "Test Arena", "city": "New York"},
                "price_ranges": None, "price_source": None}
        exact = {"id": 1, "type": "concert", "datetime_local": "2099-01-01T19:00:00",
                 "venue": card["venue"], "performers": [{"name": "Duki"}],
                 "stats": {"lowest_price": 40, "highest_price": 70, "currency": "USD"}}
        other_date = {**exact, "id": 2, "datetime_local": "2099-01-02T19:00:00"}
        with patch.multiple(seatgeek.settings, seatgeek_client_id="test", seatgeek_client_secret="test"), \
                patch.object(seatgeek.httpx, "get") as request:
            for events, expected in (
                ([exact, other_date], "SeatGeek"),
                ([other_date], None),
                ([{**exact, "stats": {}}], None),
                ([exact, {**exact, "id": 3}], None),
                ([{**exact, "title": "Duki VIP Package"}], None),
                ([exact, {**exact, "id": 4, "datetime_local": "2099-01-01T21:30:00"}], "SeatGeek"),
                ([{**exact, "datetime_local": "2099-01-01T21:30:00"}], None),
            ):
                with self.subTest(events=events):
                    seatgeek._cache.clear()
                    request.return_value.json.return_value = {"events": events, "meta": {"total": len(events)}}
                    result = tm.add_fallback_price(card)
                    self.assertEqual(result["price_source"], expected)
                    self.assertEqual(result.get("price_kind"), "resale" if expected else None)
                    self.assertEqual(result["price_ranges"],
                                     [{"min": 40, "max": 70, "currency": "USD"}] if expected else None)
            request.reset_mock()
            own = {**card, "price_ranges": [{"min": 25, "max": 30, "currency": "EUR"}], "price_source": "Ticketmaster"}
            self.assertEqual(tm.add_fallback_price(own), own)
            request.assert_not_called()
            seatgeek._cache.clear()
            request.return_value.json.return_value = {"events": [exact], "meta": {"total": 1}}
            tm.add_fallback_price(card); tm.add_fallback_price(card)
            self.assertEqual(request.call_count, 1)
            seatgeek._cache.clear()


if __name__ == "__main__":
    unittest.main()
