"""
Data API routes for Yahoo Fantasy data.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, UserLeague
from app.services.yahoo_api import YahooAPIService
from backend.routes.auth import get_current_user

router = APIRouter()


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


# User League Endpoints


@router.get("/user/leagues")
async def get_user_leagues(
    request: Request,
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
        try:
            leagues_data = await yahoo_service.get_user_leagues(sport="nba")
        except Exception as e:
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
            user_league = (
                db.query(UserLeague)
                .filter(
                    UserLeague.user_id == user.id,
                    UserLeague.league_key == league_key,
                )
                .first()
            )

            if not user_league:
                user_league = UserLeague(
                    user_id=user.id,
                    league_key=league_key,
                    league_id=league_info.get("league_id", ""),
                    league_name=league_info.get("name"),
                    season=league_info.get("season"),
                    num_teams=league_info.get("num_teams"),
                )
                db.add(user_league)
            else:
                # Update existing
                user_league.league_name = league_info.get("name")
                user_league.season = league_info.get("season")
                user_league.num_teams = league_info.get("num_teams")

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
        return await yahoo_service.get_league_info(league_key)
    except Exception as e:
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
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """Get league standings."""
    try:
        return await yahoo_service.get_league_standings(league_key)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch standings: {str(e)}",
        )


@router.get("/league/{league_key}/scoreboard")
async def get_league_scoreboard(
    league_key: str,
    week: Optional[int] = None,
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """
    Get league scoreboard for a specific week.

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
    """
    try:
        return await yahoo_service.get_league_scoreboard(league_key, week)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch scoreboard: {str(e)}",
        )


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
    yahoo_service: YahooAPIService = Depends(get_yahoo_service),
) -> dict:
    """
    Get matchups for a specific week (for Pick-a-Winner game).

    Args:
        league_key: Yahoo league key
        week: Week number (defaults to current week if not specified)
    """
    try:
        return await yahoo_service.get_matchups(league_key, week)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch matchups: {str(e)}",
        )
