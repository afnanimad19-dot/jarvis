"""Weather via Open-Meteo — free, no API key.

Set your default city with JARVIS_CITY in .env; "weather in <city>" overrides.
"""

import os

import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "showers", 81: "showers", 82: "heavy showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail", 99: "a thunderstorm with hail",
}


def default_city() -> str:
    return os.environ.get("JARVIS_CITY", "").strip()


async def get_weather(city: str = "") -> dict:
    city = (city or default_city()).strip()
    if not city:
        raise RuntimeError("No city set. Put JARVIS_CITY=YourCity in jarvis_hud/.env")

    async with httpx.AsyncClient(timeout=20) as client:
        geo = await client.get(GEO_URL, params={"name": city, "count": 1})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            raise RuntimeError(f"Couldn't find a city called {city!r}.")
        place = results[0]

        forecast = await client.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        forecast.raise_for_status()
        data = forecast.json()

    current = data.get("current", {})
    daily = data.get("daily", {})
    return {
        "city": place.get("name", city),
        "country": place.get("country", ""),
        "description": WMO.get(current.get("weather_code"), "unknown conditions"),
        "temp_c": current.get("temperature_2m"),
        "feels_c": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_kmh": current.get("wind_speed_10m"),
        "high_c": (daily.get("temperature_2m_max") or [None])[0],
        "low_c": (daily.get("temperature_2m_min") or [None])[0],
        "rain_chance": (daily.get("precipitation_probability_max") or [None])[0],
    }


def spoken(w: dict) -> str:
    parts = [
        f"{w['city']}: {w['description']}, {round(w['temp_c'])} degrees",
        f"feels like {round(w['feels_c'])}",
        f"high {round(w['high_c'])}, low {round(w['low_c'])}",
    ]
    if w.get("rain_chance") is not None:
        parts.append(f"{w['rain_chance']} percent chance of rain")
    return ". ".join(parts) + "."
