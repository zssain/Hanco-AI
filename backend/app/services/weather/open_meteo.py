"""
Open-Meteo weather service integration
Free weather API for location-based weather data
"""
import httpx
from datetime import date, datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# City coordinates (lat, lon)
CITY_COORDINATES = {
    'riyadh': (24.7136, 46.6753),
    'jeddah': (21.5433, 39.1728),
    'dammam': (26.4207, 50.0888),
    'mecca': (21.3891, 39.8579),
    'medina': (24.5247, 39.5692),
    'khobar': (26.2172, 50.1971),
    'dhahran': (26.3025, 50.1419),
    'tabuk': (28.3838, 36.5550),
    'abha': (18.2164, 42.5053),
    'default': (24.7136, 46.6753)  # Default to Riyadh
}


async def get_weather_features(city: str, target_date: date) -> Dict[str, float]:
    """
    Get weather features for pricing model
    
    Args:
        city: City name (case-insensitive)
        target_date: Date to get weather for
        
    Returns:
        Dictionary with:
            - avg_temp: Average temperature in Celsius
            - rain: Total precipitation in mm
            - wind: Average wind speed in km/h
    """
    try:
        # Get coordinates
        city_key = city.lower()
        lat, lon = CITY_COORDINATES.get(city_key, CITY_COORDINATES['default'])
        
        # Build API URL
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': target_date.isoformat(),
            'end_date': target_date.isoformat(),
            'daily': 'temperature_2m_mean,precipitation_sum,windspeed_10m_max',
            'timezone': 'auto'
        }
        
        # Make request
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract daily data
        daily = data.get('daily', {})
        
        avg_temp = daily.get('temperature_2m_mean', [20.0])[0] or 20.0
        rain = daily.get('precipitation_sum', [0.0])[0] or 0.0
        wind = daily.get('windspeed_10m_max', [10.0])[0] or 10.0
        
        logger.info(f"Weather for {city} on {target_date}: temp={avg_temp}°C, rain={rain}mm, wind={wind}km/h")
        
        return {
            'avg_temp': float(avg_temp),
            'rain': float(rain),
            'wind': float(wind)
        }
        
    except httpx.HTTPError as e:
        logger.error(f"Weather API error for {city}: {str(e)}")
        # Return default values on error
        return {
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0
        }
    except Exception as e:
        logger.error(f"Unexpected error getting weather: {str(e)}")
        return {
            'avg_temp': 25.0,
            'rain': 0.0,
            'wind': 10.0
        }
