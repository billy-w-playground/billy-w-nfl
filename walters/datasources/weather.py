"""Open-Meteo forecast at stadium lat/lon for kickoff hour. Free, no key."""
from __future__ import annotations
import datetime as dt
import requests

BASE = "https://api.open-meteo.com/v1/forecast"


def kickoff_weather(lat: float, lon: float, kickoff_utc_iso: str,
                    timeout: int = 20) -> dict:
    """Return {'temp_f': float|None, 'rain': bool, 'snow': bool, 'wind_mph': float|None}.

    Open-Meteo forecasts ~16 days out; beyond that returns Nones.
    """
    ko = dt.datetime.fromisoformat(kickoff_utc_iso)
    day = ko.date().isoformat()
    try:
        r = requests.get(BASE, params=dict(
            latitude=lat, longitude=lon,
            hourly="temperature_2m,precipitation,snowfall,wind_speed_10m",
            temperature_unit="fahrenheit", wind_speed_unit="mph",
            start_date=day, end_date=day, timezone="UTC",
        ), timeout=timeout)
        r.raise_for_status()
        h = r.json().get("hourly", {})
        times = h.get("time", [])
        target = ko.strftime("%Y-%m-%dT%H:00")
        if target not in times:
            return dict(temp_f=None, rain=False, snow=False, wind_mph=None)
        i = times.index(target)
        precip = (h["precipitation"][i] or 0)
        snow = (h["snowfall"][i] or 0)
        return dict(
            temp_f=h["temperature_2m"][i],
            rain=precip > 0.02 and snow == 0,
            snow=snow > 0,
            wind_mph=h["wind_speed_10m"][i],
        )
    except Exception:
        return dict(temp_f=None, rain=False, snow=False, wind_mph=None)
