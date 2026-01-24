"""
Data API routes for Yahoo Fantasy data.

Returns clean, parsed data with caching support.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Union

# Sentinel value to indicate "use default TTL"
_USE_DEFAULT_TTL = object()

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
from app.services.transactions import TransactionService
from app.services.yahoo_api import YahooAPIService
from backend.routes.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter()

# Cache duration in minutes
CACHE_DURATION_MINUTES = 15


def is_week_complete(week: int, current_week: int) -> bool:
    """
    Determine if a week is complete based on the current week.

    A week is considered complete if it's before the current week.
    Completed weeks have final data that will never change.

    Args:
        week: The week to check
        current_week: The current week from the league

    Returns:
        True if the week is complete, False otherwise
    """
    return week < current_week


def calculate_cache_expiry(
    week: int, current_week: int
) -> Optional[datetime]:
    """
    Calculate the appropriate cache expiry based on week status.

    - Completed weeks (week < current_week): Never expire (returns None)
    - Current/future weeks: Standard TTL

    Args:
        week: The week being cached
        current_week: The current week from the league

    Returns:
        Expiry datetime, or None for completed weeks
    """
    if is_week_complete(week, current_week):
        logger.debug(f"Week {week} is complete (current={current_week}), caching indefinitely")
        return None  # Never expires
    else:
        return datetime.now(timezone.utc) + timedelta(minutes=CACHE_DURATION_MINUTES)


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
    expires_at: Union[datetime, None, object] = _USE_DEFAULT_TTL,
) -> CachedData:
    """
    Save or update cached data with smart expiry.

    Args:
        db: Database session
        league_key: Yahoo league key
        data_type: Type of data
        data: Parsed data to cache
        week: Week number (None for season-level data)
        expires_at: Cache expiry time. Three options:
            - _USE_DEFAULT_TTL (default): Uses 15-minute TTL
            - None: Cache never expires (for completed weeks)
            - datetime: Specific expiry time

    Returns:
        The cached data record
    """
    now = datetime.now(timezone.utc)

    # Determine expiry based on parameter
    if expires_at is _USE_DEFAULT_TTL:
        calculated_expires_at: Optional[datetime] = now + timedelta(minutes=CACHE_DURATION_MINUTES)
    else:
        calculated_expires_at = expires_at  # type: ignore[assignment]

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
        cache.expires_at = calculated_expires_at
    else:
        cache = CachedData(
            league_key=league_key,
            data_type=data_type,
            week=week,
            json_data=data,
            fetched_at=now,
            expires_at=calculated_expires_at,
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
    user: User = Depends(require_auth),
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
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch standings: {str(e)}",
        )

    # Parse the response
    parsed_data = parse_standings(raw_data)

    # Determine cache expiry based on week status
    current_week = parsed_data.get("league", {}).get("current_week")
    if week is not None and current_week is not None:
        # Week-specific standings for a completed week can be cached indefinitely
        expires_at = calculate_cache_expiry(week, current_week)
    else:
        # Season totals change constantly during the season
        expires_at = _USE_DEFAULT_TTL  # type: ignore[assignment]

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, week, expires_at)

    num_teams = len(parsed_data.get("teams", []))
    cache_type = "indefinite" if expires_at is None else "timed"
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
        week: Week number (defaults to current week if not specified)
        refresh: Force refresh from Yahoo API, ignoring cache

    Returns:
        Parsed scoreboard data with cache metadata
    """
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
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch scoreboard: {str(e)}",
        )

    # Parse the response
    parsed_data = parse_scoreboard(raw_data)

    # Use the week from parsed data if not specified
    actual_week = week if week is not None else parsed_data.get("week")

    # Determine cache expiry based on week status
    current_week = parsed_data.get("league", {}).get("current_week")
    if actual_week is not None and current_week is not None:
        expires_at = calculate_cache_expiry(actual_week, current_week)
    else:
        # Fallback to default TTL if we can't determine week status
        expires_at = _USE_DEFAULT_TTL  # type: ignore[assignment]

    # Cache the parsed data
    cache = save_cached_data(db, league_key, data_type, parsed_data, actual_week, expires_at)

    num_matchups = len(parsed_data.get("matchups", []))
    cache_type = "indefinite" if expires_at is None else "timed"
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
    if start_week > end_week:
        raise HTTPException(
            status_code=400,
            detail="start_week must be less than or equal to end_week",
        )

    if start_week < 1 or end_week > 19:
        raise HTTPException(
            status_code=400,
            detail="Weeks must be between 1 and 19",
        )

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
    if start_week > end_week:
        raise HTTPException(
            status_code=400,
            detail="start_week must be less than or equal to end_week",
        )

    if start_week < 1 or end_week > 19:
        raise HTTPException(
            status_code=400,
            detail="Weeks must be between 1 and 19",
        )

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
    sync: bool = False,
    db: Session = Depends(get_db),
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    user: User = Depends(require_auth),
) -> dict:
    """
    Get league transactions from database.

    If sync=True or no transactions exist, fetch from Yahoo API first.

    Args:
        league_key: Yahoo league key
        team_key: Optional team key to filter by
        transaction_type: Filter by type (add, drop, trade, add/drop)
        limit: Maximum number of results (default 50)
        offset: Number of results to skip
        sync: If true, fetch new transactions from Yahoo first
    """
    user_id = user.id
    txn_service = TransactionService(db)

    # Check if we need to sync
    total_count = txn_service.get_transaction_count(league_key)
    should_sync = sync or total_count == 0

    new_count = 0
    if should_sync:
        try:
            logger.info(f"Syncing transactions from Yahoo: league={league_key} user={user_id}")
            raw_data = await yahoo_service.get_league_transactions(league_key)
            parsed = parse_transactions(raw_data)
            new_count = txn_service.store_transactions(league_key, parsed)
            logger.info(f"Synced {new_count} new transactions: league={league_key}")
        except Exception as e:
            logger.error(f"Failed to sync transactions: league={league_key} error={e}")
            if total_count == 0:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to fetch transactions from Yahoo: {str(e)}",
                )

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

    return {
        "transactions": result,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "synced": should_sync,
        "new_transactions": new_count if should_sync else 0,
    }


@router.get("/league/{league_key}/transactions/sync")
async def sync_transactions(
    league_key: str,
    db: Session = Depends(get_db),
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
    user: User = Depends(require_auth),
) -> dict:
    """
    Fetch new transactions from Yahoo and store in database.

    Returns count of new transactions added.

    Args:
        league_key: Yahoo league key
    """
    user_id = user.id
    logger.info(f"Explicit transaction sync requested: league={league_key} user={user_id}")

    try:
        raw_data = await yahoo_service.get_league_transactions(league_key)
        parsed = parse_transactions(raw_data)

        txn_service = TransactionService(db)
        new_count = txn_service.store_transactions(league_key, parsed)
        total_count = txn_service.get_transaction_count(league_key)

        logger.info(f"Transaction sync complete: league={league_key} new={new_count} total={total_count}")

        return {
            "success": True,
            "new_transactions": new_count,
            "total_transactions": total_count,
        }
    except Exception as e:
        logger.error(f"Failed to sync transactions: league={league_key} error={e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to sync transactions from Yahoo: {str(e)}",
        )


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
