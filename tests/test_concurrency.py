import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.session import session_manager
from backend.app.core.cache import user_email_cache


class TestMultiUserConcurrency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_concurrent_sessions_and_cache_isolation(self):
        """
        Simulates 3 distinct users (Alice, Bob, Charlie) performing simultaneous
        operations across concurrent threads. Verifies strict session and cache isolation.
        """
        users = [
            {"user_id": f"user_concurrent_{i}", "email": f"user_{i}@domain.com"}
            for i in range(1, 4)
        ]

        # 1. Create sessions concurrently
        def setup_user(u):
            session = session_manager.create_session(
                email=u["email"],
                user_id=u["user_id"],
                credentials={"token": f"token_{u['user_id']}"}
            )
            return u["user_id"], session.session_id

        user_sessions = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futs = [executor.submit(setup_user, u) for u in users]
            for fut in as_completed(futs):
                uid, sid = fut.result()
                user_sessions[uid] = sid

        self.assertEqual(len(user_sessions), 3)

        # 2. Write unique user-scoped cached messages concurrently
        def write_cache(u):
            uid = u["user_id"]
            for m in range(10):
                msg_id = f"msg_{uid}_{m}"
                user_email_cache.set(uid, msg_id, {
                    "email_id": msg_id,
                    "subject": f"Private for {uid} #{m}",
                    "owner": uid
                })
            return uid

        with ThreadPoolExecutor(max_workers=3) as executor:
            futs = [executor.submit(write_cache, u) for u in users]
            for fut in as_completed(futs):
                fut.result()

        # 3. Read cache concurrently and verify NO cross-contamination
        def verify_isolation(u):
            uid = u["user_id"]
            # Verify user's own cache hits
            for m in range(10):
                own_msg_id = f"msg_{uid}_{m}"
                item = user_email_cache.get(uid, own_msg_id)
                assert item is not None, f"Expected cache hit for {own_msg_id}"
                assert item["owner"] == uid

            # Verify other users' messages are NEVER accessible
            for other in users:
                if other["user_id"] != uid:
                    other_uid = other["user_id"]
                    for m in range(10):
                        foreign_msg_id = f"msg_{other_uid}_{m}"
                        foreign_item = user_email_cache.get(uid, foreign_msg_id)
                        assert foreign_item is None, f"Cross-user cache leak detected! User {uid} accessed {foreign_msg_id}"

            return True

        with ThreadPoolExecutor(max_workers=3) as executor:
            futs = [executor.submit(verify_isolation, u) for u in users]
            for fut in as_completed(futs):
                self.assertTrue(fut.result())


if __name__ == "__main__":
    unittest.main(verbosity=2)
