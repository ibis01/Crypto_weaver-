import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from core.redis_client import redis_client
from core.database import get_db

logger = logging.getLogger(__name__)

class CommunityManager:
    """Manage community signals and discussions"""
    
    def __init__(self):
        self.signal_channels = {}
        self.discussion_rooms = {}
    
    async def post_signal(self, user_id: int, signal_data: Dict) -> Dict:
        """Post a trading signal to community"""
        with get_db() as db:
            from modules.social.models import CommunitySignal
            
            signal = CommunitySignal(
                user_id=user_id,
                symbol=signal_data['symbol'],
                signal_type=signal_data.get('type', 'analysis'),
                action=signal_data.get('action', 'neutral'),
                price_target=signal_data.get('price_target'),
                stop_loss=signal_data.get('stop_loss'),
                confidence=signal_data.get('confidence', 0.5),
                analysis=signal_data.get('analysis', ''),
                tags=signal_data.get('tags', []),
                created_at=datetime.utcnow()
            )
            
            db.add(signal)
            db.commit()
            db.refresh(signal)
            
            # Get user info for broadcast
            from modules.auth.models import User
            user = db.query(User).filter(User.id == user_id).first()
            
            # Prepare broadcast message
            broadcast_data = {
                'signal_id': signal.id,
                'user_id': user_id,
                'username': user.username if user else f"Trader{user_id}",
                'symbol': signal.symbol,
                'action': signal.action,
                'analysis': signal.analysis,
                'confidence': signal.confidence,
                'timestamp': signal.created_at.isoformat(),
                'likes': 0,
                'comments': 0
            }
            
            # Broadcast to community
            await redis_client.publish(
                "community:signals:new",
                json.dumps(broadcast_data)
            )
            
            logger.info(f"User {user_id} posted signal for {signal.symbol}")
            return broadcast_data
    
    async def get_recent_signals(self, limit: int = 20, symbol: Optional[str] = None) -> List[Dict]:
        """Get recent community signals"""
        with get_db() as db:
            from modules.social.models import CommunitySignal
            from modules.auth.models import User
            
            query = db.query(CommunitySignal, User.username).join(
                User, CommunitySignal.user_id == User.id
            )
            
            if symbol:
                query = query.filter(CommunitySignal.symbol == symbol)
            
            signals = query.order_by(
                CommunitySignal.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for signal, username in signals:
                # Count likes and comments
                likes = db.query(func.count()).filter(
                    SignalLike.signal_id == signal.id
                ).scalar() or 0
                
                comments = db.query(func.count()).filter(
                    SignalComment.signal_id == signal.id
                ).scalar() or 0
                
                result.append({
                    'signal_id': signal.id,
                    'user_id': signal.user_id,
                    'username': username,
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'analysis': signal.analysis,
                    'confidence': signal.confidence,
                    'price_target': float(signal.price_target) if signal.price_target else None,
                    'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                    'tags': signal.tags or [],
                    'created_at': signal.created_at.isoformat(),
                    'likes': likes,
                    'comments': comments
                })
            
            return result
    
    async def like_signal(self, user_id: int, signal_id: int) -> bool:
        """Like a community signal"""
        with get_db() as db:
            from modules.social.models import SignalLike
            
            # Check if already liked
            existing = db.query(SignalLike).filter(
                SignalLike.user_id == user_id,
                SignalLike.signal_id == signal_id
            ).first()
            
            if existing:
                return False  # Already liked
            
            # Add like
            like = SignalLike(
                user_id=user_id,
                signal_id=signal_id,
                created_at=datetime.utcnow()
            )
            
            db.add(like)
            db.commit()
            
            # Publish like event
            await redis_client.publish(
                f"community:signals:{signal_id}:likes",
                json.dumps({
                    'signal_id': signal_id,
                    'user_id': user_id,
                    'total_likes': await self.get_signal_likes(signal_id),
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            
            return True
    
    async def comment_on_signal(self, user_id: int, signal_id: int, comment: str) -> Dict:
        """Add comment to a signal"""
        with get_db() as db:
            from modules.social.models import SignalComment
            from modules.auth.models import User
            
            comment_obj = SignalComment(
                user_id=user_id,
                signal_id=signal_id,
                comment=comment,
                created_at=datetime.utcnow()
            )
            
            db.add(comment_obj)
            db.commit()
            db.refresh(comment_obj)
            
            # Get user info
            user = db.query(User).filter(User.id == user_id).first()
            
            comment_data = {
                'comment_id': comment_obj.id,
                'signal_id': signal_id,
                'user_id': user_id,
                'username': user.username if user else f"Trader{user_id}",
                'comment': comment,
                'created_at': comment_obj.created_at.isoformat()
            }
            
            # Publish comment
            await redis_client.publish(
                f"community:signals:{signal_id}:comments",
                json.dumps(comment_data)
            )
            
            return comment_data
    
    async def get_signal_likes(self, signal_id: int) -> int:
        """Get total likes for a signal"""
        with get_db() as db:
            from modules.social.models import SignalLike
            
            return db.query(func.count()).filter(
                SignalLike.signal_id == signal_id
            ).scalar() or 0
    
    async def get_signal_comments(self, signal_id: int, limit: int = 50) -> List[Dict]:
        """Get comments for a signal"""
        with get_db() as db:
            from modules.social.models import SignalComment
            from modules.auth.models import User
            
            comments = db.query(SignalComment, User.username).join(
                User, SignalComment.user_id == User.id
            ).filter(
                SignalComment.signal_id == signal_id
            ).order_by(
                SignalComment.created_at.asc()
            ).limit(limit).all()
            
            return [
                {
                    'comment_id': comment.id,
                    'user_id': comment.user_id,
                    'username': username,
                    'comment': comment.comment,
                    'created_at': comment.created_at.isoformat()
                }
                for comment, username in comments
            ]
    
    async def create_discussion_room(self, creator_id: int, room_data: Dict) -> Dict:
        """Create a discussion room"""
        with get_db() as db:
            from modules.social.models import DiscussionRoom
            
            room = DiscussionRoom(
                creator_id=creator_id,
                name=room_data['name'],
                description=room_data.get('description', ''),
                symbol=room_data.get('symbol'),
                is_public=room_data.get('is_public', True),
                max_participants=room_data.get('max_participants', 100),
                created_at=datetime.utcnow()
            )
            
            db.add(room)
            db.commit()
            db.refresh(room)
            
            # Add creator as participant
            await self.join_discussion_room(creator_id, room.id)
            
            return {
                'room_id': room.id,
                'name': room.name,
                'symbol': room.symbol,
                'creator_id': creator_id,
                'participant_count': 1,
                'created_at': room.created_at.isoformat()
            }
    
    async def join_discussion_room(self, user_id: int, room_id: int) -> bool:
        """Join a discussion room"""
        with get_db() as db:
            from modules.social.models import RoomParticipant
            
            # Check if already joined
            existing = db.query(RoomParticipant).filter(
                RoomParticipant.user_id == user_id,
                RoomParticipant.room_id == room_id
            ).first()
            
            if existing:
                return True  # Already joined
            
            # Check room capacity
            from modules.social.models import DiscussionRoom
            room = db.query(DiscussionRoom).filter(DiscussionRoom.id == room_id).first()
            
            if not room:
                return False
            
            current_participants = db.query(func.count()).filter(
                RoomParticipant.room_id == room_id
            ).scalar() or 0
            
            if current_participants >= room.max_participants:
                return False
            
            # Join room
            participant = RoomParticipant(
                user_id=user_id,
                room_id=room_id,
                joined_at=datetime.utcnow()
            )
            
            db.add(participant)
            db.commit()
            
            # Publish join event
            await redis_client.publish(
                f"discussion:room:{room_id}:join",
                json.dumps({
                    'room_id': room_id,
                    'user_id': user_id,
                    'participant_count': current_participants + 1,
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            
            return True
