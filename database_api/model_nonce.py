"""
This is an experiment to prevent something that I have no evidence of happening, yet.
It may be that I am overreacting.

Nonce tracking to prevent simple replay attacks via the /run endpoint.

Tracks unique keys and counts how many times each nonce has been requested.

My concern is the /run endpoint might be hit multiple times with the same query.
IRL, I have not seen this happen, but it is a concern. If I share the url, and Google picks it up, I imagine it will hit the /run endpoint at least 1 time, possible more.
PlanExe takes 10-20 minutes to run. This putting lots of jobs in the queue, that are not needed.
Primary concern. A search engine triggering a /run, which would be a waste of resources, filling up the queue.
Secondary concern. It may be the user might hit the back button and the forward button, triggering the identical job being executed multiple times.

The user might modify the nonce key, and execute PlanExe with a prompt they provide and thus bypass generate plans without paying.
However I doubt that a search engine would modify the nonce key, which is my primary concern.

If the website gets to lots of users, then a more sophisticated system is needed to keep track of what job belongs to what user.
Currently there are barely any users, so I think nonce tracking is a good start out solution.
"""
import logging
from datetime import datetime, UTC
from database_api.planexe_db_singleton import db

logger = logging.getLogger(__name__)

class NonceItem(db.Model):
    __tablename__ = 'nonces'

    # A unique identifier for the nonce record.
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # The unique nonce key, that is used with the /run endpoint.
    nonce_key = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # When the nonce was first created.
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    # When the nonce was last accessed.
    last_accessed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    # How many times this nonce has been requested.
    request_count = db.Column(db.Integer, nullable=False, default=1)

    # Optional context information about the request.
    context = db.Column(db.JSON, nullable=True, default=None)

    def __repr__(self):
        return f"<NonceItem(id={self.id}, key={self.nonce_key[:20]!r}, count={self.request_count})>"

    @classmethod
    def get_or_create(cls, nonce_key: str, context: dict = None) -> tuple['NonceItem', bool]:
        """
        Get an existing nonce or create a new one.
        
        Args:
            nonce_key: The unique key for the nonce
            context: Optional context information
            
        Returns:
            Tuple of (NonceItem, is_new) where is_new indicates if this is a new nonce
        """
        nonce = cls.query.filter_by(nonce_key=nonce_key).first()
        
        if nonce is None:
            # Create new nonce
            nonce = cls(
                nonce_key=nonce_key,
                context=context
            )
            db.session.add(nonce)
            db.session.commit()
            logger.info(f"Created new nonce: {nonce_key}")
            return nonce, True
        else:
            # Update existing nonce
            nonce.request_count += 1
            nonce.last_accessed_at = datetime.now(UTC)
            if context:
                nonce.context = context
            db.session.commit()
            logger.info(f"Nonce reused: {nonce_key} (count: {nonce.request_count})")
            return nonce, False

    @classmethod
    def cleanup_old_nonces(cls, days_old: int = 30) -> int:
        """
        Clean up nonces older than specified days.
        
        Args:
            days_old: Number of days after which nonces should be deleted
            
        Returns:
            Number of nonces deleted
        """
        from datetime import timedelta
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)
        deleted_count = cls.query.filter(cls.created_at < cutoff_date).delete()
        db.session.commit()
        logger.info(f"Cleaned up {deleted_count} old nonces")
        return deleted_count

    @classmethod
    def demo_items(cls) -> list['NonceItem']:
        """Create demo nonce items for testing."""
        nonce1 = cls(
            nonce_key="demo_nonce_12345",
            request_count=1,
            context={"user_agent": "Mozilla/5.0", "ip": "192.168.1.100"}
        )
        nonce2 = cls(
            nonce_key="demo_nonce_67890",
            request_count=5,
            context={"user_agent": "Googlebot/2.1", "ip": "66.249.66.1"}
        )
        nonce3 = cls(
            nonce_key="demo_nonce_abcdef",
            request_count=1,
            context={"user_agent": "Edg/138.0.3351.55", "ip": "2001:0db8:85a3:0000:0000:8ae2:0360:7334"}
        )
        return [nonce1, nonce2, nonce3]
