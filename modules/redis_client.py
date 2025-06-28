import redis
import json
import os
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        """Initialize Redis client with connection pooling."""
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        self.client = redis.Redis(connection_pool=self.pool)

    def set_cache(self, key, value, expire=3600):
        """Set cache with TTL (default 1 hour)."""
        try:
            self.client.setex(key, expire, json.dumps(value))
            logger.debug(f"Cache set for key: {key}")
        except redis.RedisError as e:
            logger.error(f"Error setting cache for key {key}: {str(e)}")

    def get_cache(self, key):
        """Retrieve cache value."""
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss for key: {key}")
            return None
        except redis.RedisError as e:
            logger.error(f"Error getting cache for key {key}: {str(e)}")
            return None

    def delete_cache(self, key):
        """Delete cache value."""
        try:
            self.client.delete(key)
            logger.debug(f"Cache deleted for key: {key}")
        except redis.RedisError as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")