"""Competitor scraping services"""
from app.services.competitors.crawler import (
    fetch_offers_for_provider,
    refresh_competitor_prices,
    get_supported_cities,
    get_supported_providers,
    cleanup_old_prices,
    # Branch configuration
    load_branches_from_firestore,
    get_branches_cached,
    get_cities_from_branches,
    # Aggregation functions
    compute_aggregates_for_branch_vehicle,
    save_competitor_aggregate,
    refresh_competitor_aggregates,
    # Airport quote scraping
    scrape_airport_quotes_1day
)

__all__ = [
    'fetch_offers_for_provider',
    'refresh_competitor_prices',
    'get_supported_cities',
    'get_supported_providers',
    'cleanup_old_prices',
    'load_branches_from_firestore',
    'get_branches_cached',
    'get_cities_from_branches',
    'compute_aggregates_for_branch_vehicle',
    'save_competitor_aggregate',
    'refresh_competitor_aggregates',
    'scrape_airport_quotes_1day'
]
