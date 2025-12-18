import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import heapq

from core.redis_client import redis_client
from core.database import get_db

logger = logging.getLogger(__name__)

class LeaderboardType(Enum):
    DAILY_PNL = "daily_pnl"
    WEEKLY_PNL = "weekly_pnl"
    MONTHLY_PNL = "monthly_pnl"
    TOTAL_PNL = "total_pnl"
    WIN_RATE = "win_rate"
    TRADE_COUNT = "trade_count"
    FOLLOWER_COUNT = "follower_count"

class AchievementType(Enum):
    FIRST_TRADE = "first_trade"
    FIRST_PROFIT = "first_profit"
    TEN_TRADES = "ten_trades"
    HUNDRED_TRADES = "hundred_trades"
    TOP_TRADER = "top_trader"
    COPY_TRADER = "copy_trader"
    SOCIAL_INFLUENCER = "social_influencer"
    RISK_MASTER = "risk_master"

class LeaderboardManager:
    """Real-time leaderboard management with Redis"""
    
    def __init__(self):
        self.leaderboard_keys = {
            LeaderboardType.DAILY_PNL: "leaderboard:daily_pnl",
            LeaderboardType.WEEKLY_PNL: "leaderboard:weekly_pnl",
            LeaderboardType.MONTHLY_PNL: "leaderboard:monthly_pnl",
            LeaderboardType.TOTAL_PNL: "leaderboard:total_pnl",
            LeaderboardType.WIN_RATE: "leaderboard:win_rate",
            LeaderboardType.TRADE_COUNT: "leaderboard:trade_count",
            LeaderboardType.FOLLOWER_COUNT: "leaderboard:follower_count"
        }
    
    async def update_leaderboard(self, user_id: int, metric: LeaderboardType, value: float):
        """Update leaderboard with user's score"""
        key = self.leaderboard_keys[metric]
        
        # Use Redis sorted sets for leaderboards
        await redis_client.redis.zadd(key, {str(user_id): value})
        
        # Set expiration for time-based leaderboards
        if metric in [LeaderboardType.DAILY_PNL, LeaderboardType.WEEKLY_PNL, LeaderboardType.MONTHLY_PNL]:
            if metric == LeaderboardType.DAILY_PNL:
                expire_seconds = 86400  # 24 hours
            elif metric == LeaderboardType.WEEKLY_PNL:
                expire_seconds = 604800  # 7 days
            else:  # Monthly
                expire_seconds = 2592000  # 30 days
            
            await redis_client.redis.expire(key, expire_seconds)
        
        # Publish update for real-time clients
        await redis_client.publish(
            f"leaderboard:update:{metric.value}",
            json.dumps({
                'user_id': user_id,
                'metric': metric.value,
                'value': value,
                'rank': await self.get_user_rank(user_id, metric),
                'timestamp': datetime.utcnow().isoformat()
            })
        )
    
    async def get_leaderboard(self, metric: LeaderboardType, limit: int = 100) -> List[Dict]:
        """Get leaderboard for a specific metric"""
        key = self.leaderboard_keys[metric]
        
        # Get top users from Redis sorted set
        leaderboard_data = await redis_client.redis.zrevrange(
            key, 0, limit - 1, withscores=True
        )
        
        result = []
        for rank, (user_id_str, score) in enumerate(leaderboard_data, 1):
            user_id = int(user_id_str)
            
            # Get user details from database
            with get_db() as db:
                from modules.auth.models import User
                user = db.query(User).filter(User.id == user_id).first()
                
                if user:
                    result.append({
                        'rank': rank,
                        'user_id': user_id,
                        'username': user.username,
                        'score': float(score),
                        'avatar': await self.get_user_avatar(user_id)
                    })
        
        return result
    
    async def get_user_rank(self, user_id: int, metric: LeaderboardType) -> int:
        """Get user's rank in a specific leaderboard"""
        key = self.leaderboard_keys[metric]
        
        # Get rank from Redis (0-indexed, so add 1)
        rank = await redis_client.redis.zrevrank(key, str(user_id))
        return rank + 1 if rank is not None else 0
    
    async def get_user_stats(self, user_id: int) -> Dict:
        """Get comprehensive user stats for leaderboards"""
        with get_db() as db:
            from modules.social.models import TraderStats
            
            stats = db.query(TraderStats).filter(
                TraderStats.user_id == user_id
            ).first()
            
            if not stats:
                return {}
            
            # Calculate additional metrics
            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            # Get today's PnL
            from modules.trading.models import PaperTrade
            today_trades = db.query(PaperTrade).filter(
                PaperTrade.user_id == user_id,
                PaperTrade.created_at >= start_of_day
            ).all()
            
            daily_pnl = sum(trade.profit_loss or 0 for trade in today_trades)
            
            return {
                'user_id': user_id,
                'total_pnl': float(stats.total_pnl or 0),
                'daily_pnl': float(daily_pnl),
                'weekly_pnl': float(stats.weekly_pnl or 0),
                'monthly_pnl': float(stats.monthly_pnl or 0),
                'win_rate': float(stats.win_rate or 0),
                'total_trades': stats.total_trades or 0,
                'follower_count': stats.follower_count or 0,
                'copied_trades': stats.copied_trades or 0,
                'risk_score': stats.risk_score or 0,
                'achievements': await self.get_user_achievements(user_id)
            }
    
    async def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Get user's unlocked achievements"""
        with get_db() as db:
            from modules.social.models import UserAchievement
            
            achievements = db.query(UserAchievement).filter(
                UserAchievement.user_id == user_id
            ).all()
            
            return [
                {
                    'type': achievement.achievement_type,
                    'unlocked_at': achievement.unlocked_at.isoformat(),
                    'title': self._get_achievement_title(achievement.achievement_type),
                    'description': self._get_achievement_description(achievement.achievement_type),
                    'badge': self._get_achievement_badge(achievement.achievement_type)
                }
                for achievement in achievements
            ]
    
    def _get_achievement_title(self, achievement_type: str) -> str:
        """Get achievement title"""
        titles = {
            'first_trade': "First Trade",
            'first_profit': "First Profit",
            'ten_trades': "Active Trader",
            'hundred_trades': "Trading Veteran",
            'top_trader': "Top Trader",
            'copy_trader': "Copy Trader",
            'social_influencer': "Social Influencer",
            'risk_master': "Risk Master"
        }
        return titles.get(achievement_type, "Achievement")
    
    def _get_achievement_description(self, achievement_type: str) -> str:
        """Get achievement description"""
        descriptions = {
            'first_trade': "Executed your first trade",
            'first_profit': "Made your first profitable trade",
            'ten_trades': "Completed 10 trades",
            'hundred_trades': "Completed 100 trades",
            'top_trader': "Ranked in top 10 traders",
            'copy_trader': "Had your trade copied by 10+ followers",
            'social_influencer': "Gained 50+ followers",
            'risk_master': "Maintained risk score > 90 for 30 days"
        }
        return descriptions.get(achievement_type, "")
    
    def _get_achievement_badge(self, achievement_type: str) -> str:
        """Get achievement badge emoji"""
        badges = {
            'first_trade': "🎯",
            'first_profit': "💰",
            'ten_trades': "📈",
            'hundred_trades': "👑",
            'top_trader': "🏆",
            'copy_trader': "🔄",
            'social_influencer': "🌟",
            'risk_master': "🛡️"
        }
        return badges.get(achievement_type, "🏅")
    
    async def check_and_award_achievements(self, user_id: int):
        """Check and award achievements based on user activity"""
        with get_db() as db:
            from modules.social.models import UserAchievement, TraderStats
            from modules.trading.models import PaperTrade
            
            stats = db.query(TraderStats).filter(
                TraderStats.user_id == user_id
            ).first()
            
            if not stats:
                return []
            
            awards = []
            
            # Check for achievements
            achievements_to_check = [
                (AchievementType.FIRST_TRADE, stats.total_trades >= 1),
                (AchievementType.TEN_TRADES, stats.total_trades >= 10),
                (AchievementType.HUNDRED_TRADES, stats.total_trades >= 100),
                (AchievementType.TOP_TRADER, await self.get_user_rank(user_id, LeaderboardType.TOTAL_PNL) <= 10),
                (AchievementType.COPY_TRADER, stats.copied_trades >= 10),
                (AchievementType.SOCIAL_INFLUENCER, stats.follower_count >= 50),
                (AchievementType.RISK_MASTER, stats.risk_score >= 90)
            ]
            
            for achievement_type, condition in achievements_to_check:
                if condition:
                    # Check if already awarded
                    existing = db.query(UserAchievement).filter(
                        UserAchievement.user_id == user_id,
                        UserAchievement.achievement_type == achievement_type.value
                    ).first()
                    
                    if not existing:
                        # Award achievement
                        achievement = UserAchievement(
                            user_id=user_id,
                            achievement_type=achievement_type.value,
                            unlocked_at=datetime.utcnow()
                        )
                        db.add(achievement)
                        awards.append(achievement_type.value)
            
            if awards:
                db.commit()
                
                # Publish achievement awards
                await redis_client.publish(
                    f"achievements:awarded:{user_id}",
                    json.dumps({
                        'user_id': user_id,
                        'achievements': awards,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                )
            
            return awards
    
    async def get_user_avatar(self, user_id: int) -> str:
        """Get user avatar URL or emoji"""
        # In production, store avatars in database or CDN
        # For now, generate deterministic avatar based on user_id
        avatars = ["👤", "🧑‍💼", "👨‍🚀", "👩‍💻", "🧑‍🎨", "👨‍🔬", "👩‍🚒", "🧑‍🍳", "👨‍🎤", "👩‍🏫"]
        avatar_index = user_id % len(avatars)
        return avatars[avatar_index]
