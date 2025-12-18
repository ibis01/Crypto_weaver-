import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import hashlib
import secrets

from core.database import get_db
from core.redis_client import redis_client
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class UserProfileManager:
    """Manage user profiles and social features"""
    
    def __init__(self):
        self.profile_cache = {}
        
    async def get_user_profile(self, user_id: int, viewer_id: Optional[int] = None) -> Dict:
        """Get comprehensive user profile"""
        with get_db() as db:
            from modules.auth.models import User
            from modules.social.models import TraderStats, UserAchievement
            
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValidationError(f"User {user_id} not found")
            
            # Get trader stats
            stats = db.query(TraderStats).filter(
                TraderStats.user_id == user_id
            ).first()
            
            # Get achievements
            achievements = db.query(UserAchievement).filter(
                UserAchievement.user_id == user_id
            ).order_by(
                UserAchievement.unlocked_at.desc()
            ).limit(10).all()
            
            # Calculate social metrics
            follower_count = await self.get_follower_count(user_id)
            following_count = await self.get_following_count(user_id)
            
            # Check if viewer is following this user
            is_following = False
            if viewer_id:
                is_following = await self.is_following(viewer_id, user_id)
            
            profile = {
                'user_id': user_id,
                'username': user.username,
                'display_name': user.display_name or user.username,
                'bio': user.bio or '',
                'avatar': await self.get_user_avatar_url(user_id),
                'join_date': user.created_at.isoformat() if user.created_at else None,
                'last_active': user.last_active.isoformat() if user.last_active else None,
                
                # Trading stats
                'total_pnl': float(stats.total_pnl or 0) if stats else 0,
                'win_rate': float(stats.win_rate or 0) if stats else 0,
                'total_trades': stats.total_trades or 0 if stats else 0,
                'risk_score': stats.risk_score or 0 if stats else 0,
                'preferred_symbols': user.settings.get('preferred_symbols', []) if user.settings else [],
                
                # Social stats
                'follower_count': follower_count,
                'following_count': following_count,
                'is_following': is_following,
                'social_score': await self.calculate_social_score(user_id),
                
                # Achievements
                'achievements': [
                    {
                        'type': achievement.achievement_type,
                        'title': await self.get_achievement_title(achievement.achievement_type),
                        'unlocked_at': achievement.unlocked_at.isoformat(),
                        'badge': await self.get_achievement_badge(achievement.achievement_type)
                    }
                    for achievement in achievements
                ],
                
                # Public trading history (last 10 trades)
                'recent_trades': await self.get_public_trades(user_id, limit=10),
                
                # Community activity
                'signals_posted': await self.get_signals_posted(user_id),
                'community_rank': await self.get_community_rank(user_id)
            }
            
            # Cache profile
            cache_key = f"profile:{user_id}"
            await redis_client.cache_set(cache_key, profile, expire=300)
            
            return profile
    
    async def update_profile(self, user_id: int, updates: Dict) -> Dict:
        """Update user profile"""
        with get_db() as db:
            from modules.auth.models import User
            
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValidationError(f"User {user_id} not found")
            
            # Update allowed fields
            allowed_fields = ['display_name', 'bio', 'avatar_url', 'location', 'website']
            
            for field in allowed_fields:
                if field in updates:
                    setattr(user, field, updates[field])
            
            # Update settings if provided
            if 'settings' in updates:
                if not user.settings:
                    user.settings = {}
                user.settings.update(updates['settings'])
            
            user.last_active = datetime.utcnow()
            db.commit()
            
            # Clear profile cache
            await redis_client.redis.delete(f"profile:{user_id}")
            
            return await self.get_user_profile(user_id)
    
    async def get_follower_count(self, user_id: int) -> int:
        """Get number of followers"""
        with get_db() as db:
            from modules.social.models import FollowRelationship
            
            return db.query(func.count()).filter(
                FollowRelationship.trader_id == user_id
            ).scalar() or 0
    
    async def get_following_count(self, user_id: int) -> int:
        """Get number of users being followed"""
        with get_db() as db:
            from modules.social.models import FollowRelationship
            
            return db.query(func.count()).filter(
                FollowRelationship.follower_id == user_id
            ).scalar() or 0
    
    async def is_following(self, follower_id: int, trader_id: int) -> bool:
        """Check if user is following another user"""
        with get_db() as db:
            from modules.social.models import FollowRelationship
            
            return db.query(FollowRelationship).filter(
                FollowRelationship.follower_id == follower_id,
                FollowRelationship.trader_id == trader_id
            ).first() is not None
    
    async def calculate_social_score(self, user_id: int) -> float:
        """Calculate user's social score (0-100)"""
        score = 50  # Base score
        
        # Add points for followers
        follower_count = await self.get_follower_count(user_id)
        score += min(follower_count * 0.5, 20)  # Max 20 points
        
        # Add points for signals posted
        signals_posted = await self.get_signals_posted(user_id)
        score += min(signals_posted * 0.2, 15)  # Max 15 points
        
        # Add points for achievements
        with get_db() as db:
            from modules.social.models import UserAchievement
            achievements = db.query(func.count()).filter(
                UserAchievement.user_id == user_id
            ).scalar() or 0
        
        score += min(achievements * 2, 15)  # Max 15 points
        
        return min(score, 100)
    
    async def get_public_trades(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's public trades"""
        with get_db() as db:
            from modules.trading.models import PaperTrade
            
            trades = db.query(PaperTrade).filter(
                PaperTrade.user_id == user_id,
                PaperTrade.is_public == True
            ).order_by(
                PaperTrade.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'entry_price': float(trade.entry_price) if trade.entry_price else None,
                    'exit_price': float(trade.exit_price) if trade.exit_price else None,
                    'profit_loss': float(trade.profit_loss) if trade.profit_loss else None,
                    'created_at': trade.created_at.isoformat() if trade.created_at else None,
                    'type': trade.trade_type
                }
                for trade in trades
            ]
    
    async def get_signals_posted(self, user_id: int) -> int:
        """Get number of signals posted by user"""
        with get_db() as db:
            from modules.social.models import CommunitySignal
            
            return db.query(func.count()).filter(
                CommunitySignal.user_id == user_id
            ).scalar() or 0
    
    async def get_community_rank(self, user_id: int) -> int:
        """Get user's rank in community"""
        # Simplified ranking based on social score
        with get_db() as db:
            from modules.auth.models import User
            
            # Get all users
            users = db.query(User.id).all()
            
            # Calculate social scores for all users
            user_scores = []
            for (user_id_db,) in users[:100]:  # Limit to first 100 for performance
                score = await self.calculate_social_score(user_id_db)
                user_scores.append((user_id_db, score))
            
            # Sort by score
            user_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Find rank
            for rank, (uid, score) in enumerate(user_scores, 1):
                if uid == user_id:
                    return rank
            
            return len(user_scores) + 1
    
    async def get_user_avatar_url(self, user_id: int) -> str:
        """Get user's avatar URL"""
        # In production, this would fetch from database/CDN
        # For now, generate deterministic avatar
        avatars = [
            "https://api.dicebear.com/7.x/avataaars/svg?seed=trader1",
            "https://api.dicebear.com/7.x/avataaars/svg?seed=trader2",
            "https://api.dicebear.com/7.x/avataaars/svg?seed=trader3",
            "https://api.dicebear.com/7.x/avataaars/svg?seed=trader4",
            "https://api.dicebear.com/7.x/avataaars/svg?seed=trader5"
        ]
        avatar_index = user_id % len(avatars)
        return avatars[avatar_index]
    
    async def get_achievement_title(self, achievement_type: str) -> str:
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
    
    async def get_achievement_badge(self, achievement_type: str) -> str:
        """Get achievement badge"""
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

class ReferralManager:
    """Manage referral system"""
    
    def __init__(self):
        self.referral_cache = {}
    
    async def generate_referral_code(self, user_id: int) -> str:
        """Generate unique referral code for user"""
        with get_db() as db:
            from modules.social.models import ReferralCode
            
            # Check if user already has a referral code
            existing = db.query(ReferralCode).filter(
                ReferralCode.user_id == user_id,
                ReferralCode.expires_at > datetime.utcnow()
            ).first()
            
            if existing:
                return existing.code
            
            # Generate unique code
            code = self._generate_unique_code()
            
            referral = ReferralCode(
                user_id=user_id,
                code=code,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=365)  # 1 year
            )
            
            db.add(referral)
            db.commit()
            
            return code
    
    def _generate_unique_code(self, length: int = 8) -> str:
        """Generate unique referral code"""
        import random
        import string
        
        # Generate readable code (mix of letters and numbers)
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=length))
            # Check if code is unique (in production, check database)
            if not self._is_code_exists(code):
                return code
    
    def _is_code_exists(self, code: str) -> bool:
        """Check if referral code exists"""
        # In production, check database
        return False
    
    async def process_referral(self, new_user_id: int, referral_code: str) -> bool:
        """Process referral when new user signs up"""
        with get_db() as db:
            from modules.social.models import ReferralCode, Referral
            from modules.auth.models import User
            
            # Find valid referral code
            referral_code_obj = db.query(ReferralCode).filter(
                ReferralCode.code == referral_code,
                ReferralCode.expires_at > datetime.utcnow()
            ).first()
            
            if not referral_code_obj:
                return False
            
            # Create referral record
            referral = Referral(
                referrer_id=referral_code_obj.user_id,
                referred_id=new_user_id,
                code_used=referral_code,
                created_at=datetime.utcnow(),
                status='pending'
            )
            
            db.add(referral)
            db.commit()
            
            # Award referral bonus
            await self.award_referral_bonus(referral_code_obj.user_id, new_user_id)
            
            return True
    
    async def award_referral_bonus(self, referrer_id: int, referred_id: int):
        """Award bonus to referrer and referred user"""
        with get_db() as db:
            from modules.social.models import ReferralBonus
            
            # Award referrer
            referrer_bonus = ReferralBonus(
                user_id=referrer_id,
                referral_id=None,  # Will be set after commit
                amount=10.00,  # $10 bonus
                currency='USD',
                bonus_type='referrer',
                awarded_at=datetime.utcnow()
            )
            
            # Award referred user
            referred_bonus = ReferralBonus(
                user_id=referred_id,
                referral_id=None,
                amount=5.00,  # $5 bonus
                currency='USD',
                bonus_type='referred',
                awarded_at=datetime.utcnow()
            )
            
            db.add(referrer_bonus)
            db.add(referred_bonus)
            db.commit()
            
            # Publish bonus awards
            await redis_client.publish(
                f"referral:bonus:{referrer_id}",
                json.dumps({
                    'user_id': referrer_id,
                    'bonus_amount': 10.00,
                    'bonus_type': 'referrer',
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            
            await redis_client.publish(
                f"referral:bonus:{referred_id}",
                json.dumps({
                    'user_id': referred_id,
                    'bonus_amount': 5.00,
                    'bonus_type': 'referred',
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
    
    async def get_referral_stats(self, user_id: int) -> Dict:
        """Get user's referral statistics"""
        with get_db() as db:
            from modules.social.models import Referral, ReferralBonus
            
            # Count referrals
            total_referrals = db.query(func.count()).filter(
                Referral.referrer_id == user_id
            ).scalar() or 0
            
            successful_referrals = db.query(func.count()).filter(
                Referral.referrer_id == user_id,
                Referral.status == 'completed'
            ).scalar() or 0
            
            # Calculate total bonus earned
            total_bonus = db.query(func.sum(ReferralBonus.amount)).filter(
                ReferralBonus.user_id == user_id,
                ReferralBonus.bonus_type == 'referrer'
            ).scalar() or 0
            
            # Get referral code
            referral_code = await self.generate_referral_code(user_id)
            
            return {
                'referral_code': referral_code,
                'total_referrals': total_referrals,
                'successful_referrals': successful_referrals,
                'total_bonus_earned': float(total_bonus),
                'referral_url': f"https://t.me/CryptoWeaverBot?start=ref_{referral_code}",
                'ranking': await self.get_referral_ranking(user_id)
            }
    
    async def get_referral_ranking(self, user_id: int) -> int:
        """Get user's ranking in referral leaderboard"""
        with get_db() as db:
            from modules.social.models import Referral
            
            # Get all users by referral count
            user_ref_counts = db.query(
                Referral.referrer_id,
                func.count().label('ref_count')
            ).group_by(
                Referral.referrer_id
            ).order_by(
                func.count().desc()
            ).all()
            
            # Find user's rank
            for rank, (ref_user_id, count) in enumerate(user_ref_counts, 1):
                if ref_user_id == user_id:
                    return rank
            
            return len(user_ref_counts) + 1
