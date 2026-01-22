"""
Data API routes for Yahoo Fantasy data.

Returns clean, parsed data with caching support.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, UserLeague, CachedData
from app.logging_config import get_logger
from app.parsing.standings import parse_standings
from app.parsing.scoreboard import (
    parse_scoreboard,
    parse_weekly_totals,
    parse_weekly_rankings,
    parse_head_to_head_matrix,
)
from app.services.yahoo_api import YahooAPIService
from backend.routes.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter()

# Cache duration in minutes
CACHE_DURATION_MINUTES = 15


def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    """
    Dependency that requires authentication.

    Raises:
        HTTPException: If user is not authenticated
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_yahoo_service(
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> YahooAPIService:
    """
    Get an authenticated Yahoo API service for the current user.

    Raises:
        HTTPException: If user has no valid token
    """
    if not user.oauth_token or user.oauth_token.is_expired:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please log in again.",
        )

    return YahooAPIService(db=db, user=user)


def get_cached_data(
    db: Session,
    league_key: str,
    data_type: str,
    week: Optional[int] = None,
) -> Optional[CachedData]:
    """
    Get cached data if it exists and is not stale.

    Args:
        db: Database session
        league_key: Yahoo league key
        data_type: Type of data (standings, scoreboard, etc.)
        week: Week number (None for season-level data)

    Returns:
        CachedData if valid cache exists, None otherwise
    """
    cache = (
        db.query(CachedData)
        .filter(
            CachedData.league_key == league_key,
            CachedData.data_type == data_type,
            CachedData.week == week,
        )
        .first()
    )

    if cache and not cache.is_stale:
        return cache

    return None


def save_cached_data(
    db: Session,
    league_key: str,
    data_type: str,
    data: dict,
    week: Optional[int] = None,
) -> CachedData:
    """
    Save or update cached data.

    Args:
        db: Database session
        league_key: Yahoo league key
        data_type: Type of data
        data: Parsed data to cache
        week: Week number (None for season-level data)

    Returns:
        The cached data record
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=CACHE_DURATION_MINUTES)

    # Find existing cache entry
    cache = (
        db.query(CachedData)
        .filter(
            CachedData.league_key == league_key,
            CachedData.data_type == data_type,
            CachedData.week == week,
        )
        .first()
    )

    if cache:
        cache.json_data = data
        cache.fetched_at = now
        cache.expires_at = expires_at
    else:
        cache = CachedData(
            league_key=league_key,
            data_type=data_type,
            week=week,
            json_data=data,
            fetched_at=now,
            expires_at=expires_at,
        )
        db.add(cache)

    db.commit()
    db.refresh(cache)
    return cache


def format_cache_metadata(cache: Optional[CachedData]) -> dict:
    """
    Format cache metadata for API response.

    Args:
        cache: CachedData record or None

    Returns:
        Dictionary with cache info
    """
    if not cache:
        return {
            "cached": False,
            "fetched_at": None,
            "expires_at": None,
        }

    fetched_at = cache.fetched_at
    if fetched_at and fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    expires_at = cache.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return {
        "cached": True,
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


# User League Endpoints


@router.get("/user/leagues")
async def get_user_leagues(
    sync: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> List[dict]:
    """
    Get all leagues for the current user.

    Args:
        sync: If True, fetch fresh data from Yahoo and update database

    Returns:
        List of league information
    """
    if sync:
        # Fetch from Yahoo API
        logger.info(f"Syncing leagues for user {user.id}")
        try:
            leagues_data = await yahoo_service.get_user_leagues(sport="nba")
            logger.debug(f"Fetched {len(leagues_data)} leagues from Yahoo")
        except Exception as e:
            logger.error(f"Failed to fetch leagues from Yahoo: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch leagues from Yahoo: {str(e)}",
            )

        # Update database
        for league_info in leagues_data:
            league_key = league_info.get("league_key")
            if not league_key:
                continue

            # Find or create UserLeague
            existing_league = (
                db.query(UserLeague)
                .filter(
                    UserLeague.user_id == user.id,
                    UserLeague.league_key == league_key,
                )
                .first()
            )

            if existing_league is None:
                # Create new
                new_league = UserLeague(
                    user_id=user.id,
                    league_key=league_key,
                    league_id=league_info.get("league_id", ""),
                    league_name=league_info.get("name"),
                    season=league_info.get("season"),
                    num_teams=league_info.get("num_teams"),
                )
                db.add(new_league)
            else:
                # Update existing
                existing_league.league_name = league_info.get("name", "")
                existing_league.season = league_info.get("season", "")
                existing_league.num_teams = league_info.get("num_teams", "")

        db.commit()

    # Return from database
    user_leagues = db.query(UserLeague).filter(UserLeague.user_id == user.id).all()

    return [
        {
            "id": ul.id,
            "league_key": ul.league_key,
            "league_id": ul.league_id,
            "league_name": ul.league_name,
            "sport": ul.sport,
            "season": ul.season,
            "num_teams": ul.num_teams,
            "is_active": ul.is_active,
        }
        for ul in user_leagues
    ]


# League Data Endpoints


@router.get("/league/{league_key}/info")
async def get_league_info(
    league_key: str,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """Get league metadata."""
    try:
        logger.debug(f"Fetching info for league {league_key}")
        return await yahoo_service.get_league_info(league_key)
    except Exception as e:
        logger.error(f"Failed to fetch league info for {league_key}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch league info: {str(e)}",
        )


@router.get("/league/{league_key}/teams")
async def get_league_teams(
    league_key: str,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """Get all teams in a league."""
    try:
        return await yahoo_service.get_league_teams(league_key)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch teams: {str(e)}",
        )


@router.get("/league/{league_key}/standings")
async def get_league_standings(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get league standings with team stats.

    Returns parsed, clean data with caching.

    Args:
        league_key: Yahoo league key
        week: Week number (None for season totals)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed standings data with cache metadata
    """
    data_type = "standings"

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week)
        if cache:
            logger.debug(f"Returning cached standings for {league_key}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching standings from Yahoo for {league_key} (week={week})")
        raw_data = await yahoo_service.get_league_standings(league_key, week)
    except Exception as e:
        logger.error(f"Failed to fetch standings for {league_key}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch standings: {str(e)}",
        )

    # Parse the response
    parsed_data = parse_standings(raw_data)

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, week)

    return {
        "data": parsed_data,
        "cache": format_cache_metadata(cache),
    }


@router.get("/league/{league_key}/scoreboard")
async def get_league_scoreboard(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get league scoreboard for a specific week.

    Returns parsed matchup data with stat comparisons.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed scoreboard data with cache metadata
    """
    data_type = "scoreboard"

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week)
        if cache:
            logger.debug(f"Returning cached scoreboard for {league_key} week {week}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching scoreboard from Yahoo for {league_key} (week={week})")
        raw_data = await yahoo_service.get_league_scoreboard(league_key, week)
    except Exception as e:
        logger.error(f"Failed to fetch scoreboard for {league_key}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch scoreboard: {str(e)}",
        )

    # Parse the response
    parsed_data = parse_scoreboard(raw_data)

    # Use the week from parsed data if not specified
    actual_week = week if week is not None else parsed_data.get("week")

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, actual_week)

    return {
        "data": parsed_data,
        "cache": format_cache_metadata(cache),
    }


@router.get("/league/{league_key}/weekly-totals")
async def get_league_weekly_totals(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get weekly totals for all teams in the league.

    Returns a table-ready format with each team's stats for the week.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed totals data with cache metadata
    """
    # Get scoreboard data (uses caching)
    scoreboard_result = await get_league_scoreboard(
        league_key=league_key,
        week=week,
        refresh=refresh,
        yahoo_service=yahoo_service,
        db=db,
    )

    # Parse totals from scoreboard data
    parsed_scoreboard = scoreboard_result.get("data", {})
    totals_data = parse_weekly_totals(parsed_scoreboard)

    return {
        "data": totals_data,
        "cache": scoreboard_result.get("cache", {}),
    }


@router.get("/league/{league_key}/weekly-rankings")
async def get_league_weekly_rankings(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get weekly rankings for all teams in the league.

    Returns rank (1 = best) for each team in each stat category.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed rankings data with cache metadata
    """
    # Get scoreboard data (uses caching)
    scoreboard_result = await get_league_scoreboard(
        league_key=league_key,
        week=week,
        refresh=refresh,
        yahoo_service=yahoo_service,
        db=db,
    )

    # Parse rankings from scoreboard data
    parsed_scoreboard = scoreboard_result.get("data", {})
    rankings_data = parse_weekly_rankings(parsed_scoreboard)

    return {
        "data": rankings_data,
        "cache": scoreboard_result.get("cache", {}),
    }


@router.get("/league/{league_key}/weekly-h2h")
async def get_league_weekly_h2h(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get head-to-head matrix for all teams in the league.

    Simulates how each team would have performed against every other team
    based on their weekly stats.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        H2H matrix data with cache metadata
    """
    # Get scoreboard data (uses caching)
    scoreboard_result = await get_league_scoreboard(
        league_key=league_key,
        week=week,
        refresh=refresh,
        yahoo_service=yahoo_service,
        db=db,
    )

    # Parse H2H matrix from scoreboard data
    parsed_scoreboard = scoreboard_result.get("data", {})
    h2h_data = parse_head_to_head_matrix(parsed_scoreboard)

    return {
        "data": h2h_data,
        "cache": scoreboard_result.get("cache", {}),
    }


@router.get("/league/{league_key}/transactions")
async def get_league_transactions(
    league_key: str,
    transaction_type: Optional[str] = None,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """
    Get league transactions.

    Args:
        league_key: Yahoo league key
        transaction_type: Filter by type (add, drop, trade)
    """
    try:
        return await yahoo_service.get_league_transactions(league_key, transaction_type)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch transactions: {str(e)}",
        )


@router.get("/league/{league_key}/matchups")
async def get_league_matchups(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get matchups for a specific week (for Pick-a-Winner game).

    This is an alias for scoreboard that returns the same parsed data.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed matchup data with cache metadata
    """
    # Matchups use the same endpoint and data as scoreboard
    return await get_league_scoreboard(
        league_key=league_key,
        week=week,
        refresh=refresh,
        yahoo_service=yahoo_service,
        db=db,
    )
