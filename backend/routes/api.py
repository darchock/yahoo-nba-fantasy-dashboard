"""
Data API routes for Yahoo Fantasy data.

Returns clean, parsed data with caching support.
Uses lazy refresh strategy: refresh at 6 AM Eastern daily boundary.
"""

from datetime import datetime, timezone
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
    parse_periodical_totals,
    parse_periodical_rankings,
)
from app.parsing.transactions import parse_transactions
from app.parsing.helpers import extract_team_info, safe_get
from app.services.cache_utils import is_week_complete
from app.services.transactions import TransactionService
from app.services.yahoo_api import (
    YahooAPIService,
    YahooAPIError,
    YahooRateLimitError,
    YahooAuthError,
    YahooConnectionError,
    YahooTimeoutError,
)
from backend.routes.auth import get_current_user
from backend.correlation import get_correlation_id, log_prefix


def handle_yahoo_api_error(e: Exception, context: str = "") -> HTTPException:
    """
    Convert Yahoo API exceptions to appropriate HTTPExceptions.

    Args:
        e: The exception to handle
        context: Additional context for error message (e.g., "fetching standings")

    Returns:
        HTTPException with appropriate status code and message
    """
    cid = get_correlation_id()
    context_msg = f" while {context}" if context else ""

    # Build base detail message with correlation ID for traceability
    def detail_with_cid(msg: str) -> str:
        return f"{msg} (ref: {cid})" if cid else msg

    if isinstance(e, YahooRateLimitError):
        detail = f"Yahoo API rate limit exceeded{context_msg}. Please try again later."
        if e.retry_after:
            detail += f" (retry after {e.retry_after} seconds)"
        return HTTPException(status_code=429, detail=detail_with_cid(detail))

    if isinstance(e, YahooAuthError):
        return HTTPException(
            status_code=401,
            detail=detail_with_cid(f"Yahoo authentication failed{context_msg}. Please log in again."),
        )

    if isinstance(e, YahooTimeoutError):
        return HTTPException(
            status_code=504,
            detail=detail_with_cid(f"Yahoo API request timed out{context_msg}. Please try again."),
        )

    if isinstance(e, YahooConnectionError):
        return HTTPException(
            status_code=502,
            detail=detail_with_cid(f"Unable to connect to Yahoo API{context_msg}. Please try again later."),
        )

    if isinstance(e, YahooAPIError):
        status_code = e.status_code or 502
        return HTTPException(
            status_code=status_code,
            detail=detail_with_cid(f"Yahoo API error{context_msg}: {e.message}"),
        )

    # Generic fallback
    return HTTPException(
        status_code=502,
        detail=detail_with_cid(f"Failed to communicate with Yahoo API{context_msg}: {str(e)}"),
    )

logger = get_logger(__name__)

router = APIRouter()

# Week bounds for NBA fantasy season
MIN_WEEK = 1
MAX_WEEK = 19


def validate_week(week: Optional[int], required: bool = False) -> None:
    """
    Validate week parameter is within NBA fantasy season bounds.

    Args:
        week: Week number to validate (None allowed if not required)
        required: If True, week cannot be None

    Raises:
        HTTPException: If week is invalid
    """
    if week is None:
        if required:
            raise HTTPException(
                status_code=400,
                detail="Week parameter is required",
            )
        return

    if week < MIN_WEEK or week > MAX_WEEK:
        raise HTTPException(
            status_code=400,
            detail=f"Week must be between {MIN_WEEK} and {MAX_WEEK}",
        )


def validate_league_key(league_key: str) -> None:
    """
    Validate league_key matches expected Yahoo Fantasy format.

    Expected formats:
    - {sport}.l.{league_id} - e.g., nba.l.12345
    - {game_id}.l.{league_id} - e.g., 418.l.12345 (game_id is numeric)

    Args:
        league_key: League key to validate

    Raises:
        HTTPException: If league_key format is invalid
    """
    import re
    # Pattern: sport abbreviation (2-4 lowercase letters) OR game_id (numeric),
    # followed by literal ".l.", then numeric league ID
    pattern = r"^([a-z]{2,4}|\d+)\.l\.\d+$"
    if not re.match(pattern, league_key):
        raise HTTPException(
            status_code=400,
            detail="Invalid league_key format. Expected format: sport.l.league_id (e.g., nba.l.12345 or 418.l.12345)",
        )


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

    Does NOT check token expiry here - YahooAPIService.get_valid_access_token()
    handles refresh transparently using the refresh token.

    Raises:
        HTTPException: If user has no OAuth token record at all
    """
    if not user.oauth_token:
        raise HTTPException(
            status_code=401,
            detail="No Yahoo token found. Please log in again.",
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
    is_complete: bool = False,
) -> CachedData:
    """
    Save or update cached data with lazy refresh strategy.

    Args:
        db: Database session
        league_key: Yahoo league key
        data_type: Type of data
        data: Parsed data to cache
        week: Week number (None for season-level data)
        is_complete: If True, data is for a completed week and never needs refresh

    Returns:
        The cached data record
    """
    now = datetime.now(timezone.utc)

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
        cache.is_complete = is_complete  # type: ignore[assignment]
    else:
        cache = CachedData(
            league_key=league_key,
            data_type=data_type,
            week=week,
            json_data=data,
            fetched_at=now,
            is_complete=is_complete,
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
        Dictionary with cache info including lazy refresh status
    """
    if not cache:
        return {
            "cached": False,
            "fetched_at": None,
            "is_complete": False,
        }

    fetched_at = cache.fetched_at
    if fetched_at and fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    return {
        "cached": True,
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
        "is_complete": cache.is_complete or False,
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
        logger.info(f"Syncing leagues from Yahoo: user={user.id}")
        try:
            leagues_data = await yahoo_service.get_user_leagues(sport="nba")
            logger.info(f"Synced {len(leagues_data)} leagues from Yahoo: user={user.id}")
        except Exception as e:
            logger.error(f"Failed to sync leagues from Yahoo: user={user.id} error={e}")
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
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """Get league metadata with caching."""
    data_type = "league_info"
    user_id = user.id

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week=None)
        if cache:
            logger.debug(f"Cache hit: league_info league={league_key} user={user_id}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }
        logger.debug(f"Cache miss: league_info league={league_key} user={user_id}")
    else:
        logger.debug(f"Cache bypass (refresh=true): league_info league={league_key} user={user_id}")

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching league info from Yahoo: league={league_key} user={user_id}")
        raw_data = await yahoo_service.get_league_info(league_key)
    except Exception as e:
        logger.error(f"Failed to fetch league info: league={league_key} user={user_id} error={e}")
        raise handle_yahoo_api_error(e, context="fetching league info")

    # League info rarely changes - mark as complete (never needs refresh)
    cache = save_cached_data(db, league_key, data_type, raw_data, week=None, is_complete=True)
    logger.debug(f"Cached league_info: league={league_key} cache=complete")

    return {
        "data": raw_data,
        "cache": format_cache_metadata(cache),
    }


@router.get("/league/{league_key}/teams")
async def get_league_teams(
    league_key: str,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """Get all teams in a league with caching."""
    data_type = "league_teams"
    user_id = user.id

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week=None)
        if cache:
            logger.debug(f"Cache hit: league_teams league={league_key} user={user_id}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }
        logger.debug(f"Cache miss: league_teams league={league_key} user={user_id}")
    else:
        logger.debug(f"Cache bypass (refresh=true): league_teams league={league_key} user={user_id}")

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching league teams from Yahoo: league={league_key} user={user_id}")
        raw_data = await yahoo_service.get_league_teams(league_key)
    except Exception as e:
        logger.error(f"Failed to fetch teams: league={league_key} user={user_id} error={e}")
        raise handle_yahoo_api_error(e, context="fetching teams")

    # Teams don't change mid-season - mark as complete (never needs refresh)
    cache = save_cached_data(db, league_key, data_type, raw_data, week=None, is_complete=True)
    logger.debug(f"Cached league_teams: league={league_key} cache=complete")

    return {
        "data": raw_data,
        "cache": format_cache_metadata(cache),
    }


@router.get("/league/{league_key}/user/team")
async def get_user_team(
    league_key: str,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get the current user's team in a league.

    Finds the team where the manager's Yahoo GUID matches the user's GUID.

    Args:
        league_key: Yahoo league key
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        User's team info or null if not found
    """
    data_type = "league_teams"
    user_id = user.id
    user_guid = user.yahoo_guid

    # Check cache first (unless refresh requested)
    cache = None
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week=None)
        if cache:
            logger.debug(f"Cache hit: user_team lookup league={league_key} user={user_id}")
            raw_data = cache.json_data
        else:
            logger.debug(f"Cache miss: user_team lookup league={league_key} user={user_id}")

    if not cache or refresh:
        # Fetch from Yahoo API
        try:
            logger.info(f"Fetching teams from Yahoo for user_team lookup: league={league_key} user={user_id}")
            raw_data = await yahoo_service.get_league_teams(league_key)
        except Exception as e:
            logger.error(f"Failed to fetch teams: league={league_key} user={user_id} error={e}")
            raise handle_yahoo_api_error(e, context="fetching teams for user team lookup")

        # Teams don't change mid-season - mark as complete
        cache = save_cached_data(db, league_key, data_type, raw_data, week=None, is_complete=True)

    # Parse teams and find user's team
    teams_raw = safe_get(raw_data, "fantasy_content", "league", 1, "teams", default={})

    user_team = None
    for key, team_data in teams_raw.items():
        if key == "count" or not isinstance(team_data, dict):
            continue

        team_info = extract_team_info(team_data)
        if team_info.get("manager_guid") == user_guid:
            user_team = {
                "team_key": team_info.get("team_key"),
                "team_id": team_info.get("team_id"),
                "name": team_info.get("name"),
                "manager_name": team_info.get("manager_name"),
            }
            break

    if user_team:
        logger.debug(f"Found user team: league={league_key} team={user_team['team_key']} user={user_id}")
    else:
        logger.debug(f"User team not found: league={league_key} user={user_id}")

    return {
        "team": user_team,
        "cache": format_cache_metadata(cache),
    }


@router.get("/league/{league_key}/standings")
async def get_league_standings(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get league standings with team stats.

    Returns parsed, clean data with caching.

    Args:
        league_key: Yahoo league key
        week: Week number (1-19, None for season totals)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed standings data with cache metadata
    """
    # Validate inputs
    try:    
        validate_league_key(league_key)
        validate_week(week)
    except HTTPException as ex:
        logger.error(f"Validation error: league={league_key} week={week} user={user.id} error={ex.detail}")
        raise

    data_type = "standings"
    user_id = user.id

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week)
        if cache:
            logger.debug(f"Cache hit: standings league={league_key} week={week} user={user_id}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }
        logger.debug(f"Cache miss: standings league={league_key} week={week} user={user_id}")
    else:
        logger.debug(f"Cache bypass (refresh=true): standings league={league_key} week={week} user={user_id}")

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching standings from Yahoo: league={league_key} week={week} user={user_id}")
        raw_data = await yahoo_service.get_league_standings(league_key, week)
    except Exception as e:
        logger.error(f"Failed to fetch standings: league={league_key} week={week} user={user_id} error={e}")
        raise handle_yahoo_api_error(e, context="fetching standings")

    # Parse the response
    parsed_data = parse_standings(raw_data)

    # Determine if this is complete data (historical week)
    current_week = parsed_data.get("league", {}).get("current_week")
    week_is_complete = (
        week is not None
        and current_week is not None
        and is_week_complete(week, current_week)
    )

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, week, is_complete=week_is_complete)

    num_teams = len(parsed_data.get("teams", []))
    cache_type = "complete" if week_is_complete else "lazy-refresh"
    logger.debug(f"Cached standings: league={league_key} week={week} teams={num_teams} cache={cache_type}")

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
    user: User = Depends(require_auth),
) -> dict:
    """
    Get league scoreboard for a specific week.

    Returns parsed matchup data with stat comparisons.

    Args:
        league_key: Yahoo league key
        week: Week number (1-19, defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed scoreboard data with cache metadata
    """
    # Validate inputs
    try:    
        validate_league_key(league_key)
        validate_week(week)
    except HTTPException as ex:
        logger.error(f"Validation error: league={league_key} week={week} user={user.id} error={ex.detail}")
        raise

    data_type = "scoreboard"
    user_id = user.id

    # Check cache first (unless refresh requested)
    if not refresh:
        cache = get_cached_data(db, league_key, data_type, week)
        if cache:
            logger.debug(f"Cache hit: scoreboard league={league_key} week={week} user={user_id}")
            return {
                "data": cache.json_data,
                "cache": format_cache_metadata(cache),
            }
        logger.debug(f"Cache miss: scoreboard league={league_key} week={week} user={user_id}")
    else:
        logger.debug(f"Cache bypass (refresh=true): scoreboard league={league_key} week={week} user={user_id}")

    # Fetch from Yahoo API
    try:
        logger.info(f"Fetching scoreboard from Yahoo: league={league_key} week={week} user={user_id}")
        raw_data = await yahoo_service.get_league_scoreboard(league_key, week)
    except Exception as e:
        logger.error(f"Failed to fetch scoreboard: league={league_key} week={week} user={user_id} error={e}")
        raise handle_yahoo_api_error(e, context="fetching scoreboard")

    # Parse the response
    parsed_data = parse_scoreboard(raw_data)

    # Use the week from parsed data if not specified
    actual_week = week if week is not None else parsed_data.get("week")

    # Determine if this is complete data (historical week)
    current_week = parsed_data.get("league", {}).get("current_week")
    week_is_complete = (
        actual_week is not None
        and current_week is not None
        and is_week_complete(actual_week, current_week)
    )

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, actual_week, is_complete=week_is_complete)

    num_matchups = len(parsed_data.get("matchups", []))
    cache_type = "complete" if week_is_complete else "lazy-refresh"
    logger.debug(f"Cached scoreboard: league={league_key} week={actual_week} matchups={num_matchups} cache={cache_type}")

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
    user: User = Depends(require_auth),
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
        user=user,
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
    user: User = Depends(require_auth),
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
        user=user,
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
    user: User = Depends(require_auth),
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
        user=user,
    )

    # Parse H2H matrix from scoreboard data
    parsed_scoreboard = scoreboard_result.get("data", {})
    h2h_data = parse_head_to_head_matrix(parsed_scoreboard)

    return {
        "data": h2h_data,
        "cache": scoreboard_result.get("cache", {}),
    }


@router.get("/league/{league_key}/periodical-totals")
async def get_league_periodical_totals(
    league_key: str,
    start_week: int,
    end_week: int,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get aggregated totals for all teams across a week range.

    Counting stats are summed, percentage stats are averaged.

    Args:
        league_key: Yahoo league key
        start_week: First week of the period (inclusive)
        end_week: Last week of the period (inclusive)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Aggregated totals data with cache metadata
    """
    # Validate inputs
    try:    
        validate_league_key(league_key)
        validate_week(start_week, required=True)
        validate_week(end_week, required=True)

        if start_week > end_week:
            raise HTTPException(
                status_code=400,
                detail="start_week must be less than or equal to end_week",
            )
        
    except HTTPException as ex:
        logger.error(f"Validation error: league={league_key} start_week={start_week} end_week={end_week} user={user.id} error={ex.detail}")
        raise


    # Fetch scoreboard data for each week in the range
    parsed_scoreboards = []
    for week in range(start_week, end_week + 1):
        scoreboard_result = await get_league_scoreboard(
            league_key=league_key,
            week=week,
            refresh=refresh,
            yahoo_service=yahoo_service,
            db=db,
            user=user,
        )
        parsed_scoreboards.append(scoreboard_result.get("data", {}))

    # Parse aggregated totals
    totals_data = parse_periodical_totals(parsed_scoreboards)

    return {
        "data": totals_data,
        "cache": {"cached": not refresh, "note": f"Aggregated from weeks {start_week}-{end_week}"},
    }


@router.get("/league/{league_key}/periodical-rankings")
async def get_league_periodical_rankings(
    league_key: str,
    start_week: int,
    end_week: int,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get rankings for all teams based on aggregated stats across a week range.

    Args:
        league_key: Yahoo league key
        start_week: First week of the period (inclusive)
        end_week: Last week of the period (inclusive)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Rankings data with cache metadata
    """
    # Validate inputs
    try:    
        validate_league_key(league_key)
        validate_week(start_week, required=True)
        validate_week(end_week, required=True)

        if start_week > end_week:
            raise HTTPException(
                status_code=400,
                detail="start_week must be less than or equal to end_week",
            )
        
    except HTTPException as ex:
        logger.error(f"Validation error: league={league_key} start_week={start_week} end_week={end_week} user={user.id} error={ex.detail}")
        raise
    
    # Fetch scoreboard data for each week in the range
    parsed_scoreboards = []
    for week in range(start_week, end_week + 1):
        scoreboard_result = await get_league_scoreboard(
            league_key=league_key,
            week=week,
            refresh=refresh,
            yahoo_service=yahoo_service,
            db=db,
            user=user,
        )
        parsed_scoreboards.append(scoreboard_result.get("data", {}))

    # Parse aggregated rankings
    rankings_data = parse_periodical_rankings(parsed_scoreboards)

    return {
        "data": rankings_data,
        "cache": {"cached": not refresh, "note": f"Aggregated from weeks {start_week}-{end_week}"},
    }


@router.get("/league/{league_key}/transactions")
async def get_league_transactions(
    league_key: str,
    team_key: Optional[str] = None,
    transaction_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
    db: Session = Depends(get_db),
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get league transactions from database.

    Uses lazy refresh strategy: syncs from Yahoo if last sync was before 6 AM Eastern.

    Args:
        league_key: Yahoo league key
        team_key: Optional team key to filter by
        transaction_type: Filter by type (add, drop, trade, add/drop)
        limit: Maximum number of results (default 50)
        offset: Number of results to skip
        refresh: Force refresh from Yahoo, ignoring lazy refresh
    """
    user_id = user.id
    txn_service = TransactionService(db)

    # Check if we need to sync using lazy refresh strategy
    total_count = txn_service.get_transaction_count(league_key)
    should_sync = refresh or total_count == 0 or txn_service.should_sync_transactions(league_key)

    new_count = 0
    if should_sync:
        try:
            logger.info(f"Syncing transactions from Yahoo: league={league_key} user={user_id}")
            raw_data = await yahoo_service.get_league_transactions(league_key)
            parsed = parse_transactions(raw_data)
            new_count = txn_service.store_transactions(league_key, parsed)
            # Update last sync time
            txn_service.update_last_sync_time(user_id, league_key)
            logger.info(f"Synced {new_count} new transactions: league={league_key}")
        except Exception as e:
            logger.error(f"Failed to sync transactions: league={league_key} error={e}")
            if total_count == 0:
                # No cached data to fall back on - raise the error
                raise handle_yahoo_api_error(e, context="syncing transactions")
            # Otherwise, fall back to cached data (logged above)

    # Query from database
    transactions = txn_service.get_transactions(
        league_key=league_key,
        team_key=team_key,
        transaction_type=transaction_type,
        limit=limit,
        offset=offset,
    )

    # Format response
    result = []
    for txn in transactions:
        txn_data = {
            "transaction_id": txn.transaction_id,
            "type": txn.type,
            "status": txn.status,
            "timestamp": txn.timestamp,
            "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
            "players": [
                {
                    "player_id": p.player_id,
                    "player_name": p.player_name,
                    "nba_team": p.nba_team,
                    "position": p.position,
                    "action_type": p.action_type,
                    "source_type": p.source_type,
                    "source_team_key": p.source_team_key,
                    "source_team_name": p.source_team_name,
                    "destination_type": p.destination_type,
                    "destination_team_key": p.destination_team_key,
                    "destination_team_name": p.destination_team_name,
                }
                for p in txn.players
            ],
        }
        if txn.trader_team_key:
            txn_data["trader_team_key"] = txn.trader_team_key
        if txn.tradee_team_key:
            txn_data["tradee_team_key"] = txn.tradee_team_key
        result.append(txn_data)

    total_count = txn_service.get_transaction_count(league_key)

    # Get sync metadata for the response
    sync_meta = txn_service.get_sync_metadata(league_key)

    return {
        "transactions": result,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "synced": should_sync,
        "new_transactions": new_count if should_sync else 0,
        "last_sync_at": sync_meta.get("last_sync_at"),
    }


@router.get("/league/{league_key}/transactions/stats")
async def get_transaction_stats(
    league_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get transaction statistics for a league.

    Returns:
    - Manager activity (transaction counts per team)
    - Most added players
    - Most dropped players
    """
    txn_service = TransactionService(db)
    stats = txn_service.get_transaction_stats(league_key)

    return {
        "total_transactions": stats["total_transactions"],
        "manager_activity": stats["manager_activity"],
        "most_added": stats["most_added"],
        "most_dropped": stats["most_dropped"],
    }


@router.get("/league/{league_key}/matchups")
async def get_league_matchups(
    league_key: str,
    week: Optional[int] = None,
    refresh: bool = False,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
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
        user=user,
    )
