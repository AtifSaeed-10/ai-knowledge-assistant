"""
Platform layer: identity, quotas, ownership isolation, and guest migration.

Each test class runs against its own temporary database so trial counters
never leak between tests or from a developer's working database.
"""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app_platform import settings
from app_platform.auth.dependency import resolve_context
from app_platform.auth.supabase_jwt import (
    TokenError,
    bearer_token,
    clear_jwks_cache,
    verify_token,
)
from app_platform.guards import ownership
from app_platform.quotas import service as quotas
from database.db import init_db
from database.document_store import (
    create_document,
    get_document,
    reassign_documents,
    update_document_status,
)
from database.guest_store import get_guest_session, mark_guest_migrated
from memory.store import (
    conversation_owner,
    create_conversation,
    reassign_conversations,
)

JWT_SECRET = "unit-test-jwt-secret"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_token(
    subject: str,
    email: str | None = None,
    *,
    expires_in: int = 3600,
    secret: str = JWT_SECRET,
) -> str:
    """Mint a Supabase-shaped HS256 access token."""
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims = {"sub": subject, "exp": int(time.time()) + expires_in}
    if email:
        claims["email"] = email
    payload = _b64(json.dumps(claims).encode())
    signature = hmac.new(
        secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_b64(signature)}"


class TemporaryDatabase(unittest.TestCase):
    """Base class that redirects SQLite to a fresh file per test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = patch(
            "database.connection.database_path",
            return_value=os.path.join(self._tmpdir.name, "platform.db"),
        )
        self._db_patch.start()
        init_db()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def ready_document(self, filename, owner_type=None, owner_id=None) -> str:
        document_id = create_document(filename, owner_type=owner_type, owner_id=owner_id)
        update_document_status(document_id, "ready")
        return document_id


class TestGuestIdentity(TemporaryDatabase):
    def test_valid_header_becomes_a_guest_actor(self):
        context = resolve_context(None, "guest-session-aaaa1111")
        self.assertTrue(context.is_guest)
        self.assertEqual(context.actor_id, "guest-session-aaaa1111")
        self.assertEqual(context.tier, "guest")

    def test_missing_or_malformed_header_is_rejected(self):
        for header in (None, "   ", "short", "has spaces", "bad/chars"):
            with self.subTest(header=header):
                with self.assertRaises(HTTPException) as caught:
                    resolve_context(None, header)
                self.assertEqual(caught.exception.status_code, 401)

    def test_guest_trial_can_be_disabled(self):
        with patch.object(settings, "GUEST_TRIAL_ENABLED", False):
            with self.assertRaises(HTTPException) as caught:
                resolve_context(None, "guest-session-aaaa1111")
            self.assertEqual(caught.exception.status_code, 401)


class TestGuestQuotas(TemporaryDatabase):
    def setUp(self):
        super().setUp()
        self.limits = patch.multiple(
            settings,
            QUOTA_GUEST_MAX_PDFS=1,
            QUOTA_GUEST_MAX_QUESTIONS=3,
        )
        self.limits.start()
        self.addCleanup(self.limits.stop)
        self.guest = resolve_context(None, "guest-session-aaaa1111")
        self.other = resolve_context(None, "guest-session-bbbb2222")

    def test_guest_cannot_upload_a_second_pdf(self):
        quotas.check_upload_allowed(self.guest)
        self.ready_document("first.pdf", "guest", self.guest.actor_id)

        with self.assertRaises(HTTPException) as caught:
            quotas.check_upload_allowed(self.guest)

        detail = caught.exception.detail
        self.assertEqual(caught.exception.status_code, 402)
        self.assertEqual(detail["code"], "QUOTA_EXCEEDED")
        self.assertEqual(detail["resource"], "pdfs")
        self.assertEqual(detail["upgrade_hint"], "sign_in")

    def test_one_guest_reaching_the_limit_does_not_block_another(self):
        self.ready_document("first.pdf", "guest", self.guest.actor_id)
        quotas.check_upload_allowed(self.other)

    def test_deleting_a_document_frees_the_upload_slot(self):
        from index_hygiene import remove_document_completely

        document_id = self.ready_document("first.pdf", "guest", self.guest.actor_id)
        with self.assertRaises(HTTPException):
            quotas.check_upload_allowed(self.guest)

        remove_document_completely(document_id)
        quotas.check_upload_allowed(self.guest)

    def test_sixteenth_question_is_refused(self):
        for _ in range(3):
            quotas.check_question_allowed(self.guest)
            quotas.record_question(self.guest)

        with self.assertRaises(HTTPException) as caught:
            quotas.check_question_allowed(self.guest)

        detail = caught.exception.detail
        self.assertEqual(caught.exception.status_code, 402)
        self.assertEqual(detail["resource"], "questions")
        self.assertEqual(detail["used"], 3)
        self.assertEqual(detail["limit"], 3)

    def test_oversized_upload_is_refused_before_it_is_stored(self):
        with patch.object(settings, "QUOTA_MAX_PDF_MB", 1):
            quotas.check_upload_size(500 * 1024)
            with self.assertRaises(HTTPException) as caught:
                quotas.check_upload_size(3 * 1024 * 1024)
        self.assertEqual(caught.exception.status_code, 413)

    def test_usage_summary_reports_both_allowances(self):
        self.ready_document("first.pdf", "guest", self.guest.actor_id)
        quotas.record_question(self.guest)

        summary = quotas.usage_summary(self.guest)
        self.assertEqual(summary["tier"], "guest")
        self.assertEqual(summary["pdfs_used"], 1)
        self.assertEqual(summary["pdfs_limit"], 1)
        self.assertEqual(summary["questions_used"], 1)
        self.assertEqual(summary["questions_limit"], 3)
        self.assertEqual(summary["questions_window"], "trial")


class TestSupabaseTokens(unittest.TestCase):
    def setUp(self):
        self.auth = patch.multiple(
            settings,
            AUTH_PROVIDER="supabase",
            SUPABASE_JWT_SECRET=JWT_SECRET,
        )
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def test_bearer_header_parsing(self):
        self.assertEqual(bearer_token("Bearer abc"), "abc")
        self.assertEqual(bearer_token("bearer abc"), "abc")
        self.assertIsNone(bearer_token("Basic abc"))
        self.assertIsNone(bearer_token("Bearer"))
        self.assertIsNone(bearer_token(None))

    def test_valid_token_yields_its_claims(self):
        claims = verify_token(make_token("sub-a", "a@example.com"))
        self.assertEqual(claims["sub"], "sub-a")
        self.assertEqual(claims["email"], "a@example.com")

    def test_untrusted_tokens_are_rejected(self):
        forged_header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        forged_payload = _b64(json.dumps({"sub": "attacker"}).encode())

        cases = {
            "wrong secret": make_token("sub-a", secret="not-the-secret"),
            "expired": make_token("sub-a", expires_in=-10),
            "unsigned alg=none": f"{forged_header}.{forged_payload}.",
            "not a jwt": "not.a.jwt",
            "empty": "",
            "no subject": make_token(""),
        }

        for label, token in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(TokenError):
                    verify_token(token)

    def test_verification_fails_closed_when_no_secret_is_set(self):
        with patch.object(settings, "SUPABASE_JWT_SECRET", ""):
            with self.assertRaises(TokenError):
                verify_token(make_token("sub-a"))

    def test_es256_token_verifies_against_jwks(self):
        from cryptography.hazmat.primitives.asymmetric.ec import (
            ECDSA,
            SECP256R1,
            generate_private_key,
        )
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        from cryptography.hazmat.primitives.hashes import SHA256

        private = generate_private_key(SECP256R1())
        numbers = private.public_key().public_numbers()
        header = _b64(json.dumps({
            "alg": "ES256",
            "typ": "JWT",
            "kid": "test-es256",
        }).encode())
        payload = _b64(json.dumps({
            "sub": "sub-es",
            "email": "es@example.com",
            "exp": int(time.time()) + 3600,
        }).encode())
        der = private.sign(f"{header}.{payload}".encode("ascii"), ECDSA(SHA256()))
        r, s = decode_dss_signature(der)
        signature = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        token = f"{header}.{payload}.{signature}"
        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "kid": "test-es256",
            "x": _b64(numbers.x.to_bytes(32, "big")),
            "y": _b64(numbers.y.to_bytes(32, "big")),
        }

        clear_jwks_cache()
        with patch(
            "app_platform.auth.supabase_jwt.fetch_jwks",
            return_value=[jwk],
        ):
            claims = verify_token(token)
        self.assertEqual(claims["sub"], "sub-es")
        self.assertEqual(claims["email"], "es@example.com")

    def test_es256_token_is_rejected_for_the_wrong_key(self):
        header = _b64(json.dumps({"alg": "ES256", "typ": "JWT"}).encode())
        payload = _b64(json.dumps({
            "sub": "sub-es",
            "exp": int(time.time()) + 3600,
        }).encode())
        token = f"{header}.{payload}.{_b64(b'\\x00' * 64)}"
        clear_jwks_cache()
        with patch(
            "app_platform.auth.supabase_jwt.fetch_jwks",
            return_value=[],
        ):
            with self.assertRaises(TokenError):
                verify_token(token)


class TestUserIdentity(TemporaryDatabase):
    def setUp(self):
        super().setUp()
        self.auth = patch.multiple(
            settings,
            AUTH_PROVIDER="supabase",
            SUPABASE_JWT_SECRET=JWT_SECRET,
        )
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def test_token_wins_over_a_leftover_guest_header(self):
        context = resolve_context(
            f"Bearer {make_token('sub-a', 'a@example.com')}",
            "guest-session-aaaa1111",
        )
        self.assertTrue(context.is_user)
        self.assertEqual(context.email, "a@example.com")
        self.assertEqual(context.tier, "free")

    def test_internal_user_id_is_stable_across_sign_ins(self):
        first = resolve_context(f"Bearer {make_token('sub-a', 'a@example.com')}", None)
        second = resolve_context(f"Bearer {make_token('sub-a', 'a@example.com')}", None)
        self.assertEqual(first.actor_id, second.actor_id)

    def test_different_subjects_get_different_user_ids(self):
        first = resolve_context(f"Bearer {make_token('sub-a')}", None)
        second = resolve_context(f"Bearer {make_token('sub-b')}", None)
        self.assertNotEqual(first.actor_id, second.actor_id)

    def test_a_token_is_refused_when_auth_is_off(self):
        with patch.object(settings, "AUTH_PROVIDER", "none"):
            with self.assertRaises(HTTPException) as caught:
                resolve_context(f"Bearer {make_token('sub-a')}", None)
        self.assertEqual(caught.exception.status_code, 401)


class TestOwnershipIsolation(TemporaryDatabase):
    def setUp(self):
        super().setUp()
        self.a = resolve_context(None, "guest-session-aaaa1111")
        self.b = resolve_context(None, "guest-session-bbbb2222")
        self.doc_a = self.ready_document("a.pdf", "guest", self.a.actor_id)
        self.doc_b = self.ready_document("b.pdf", "guest", self.b.actor_id)

    def test_another_actors_document_is_forbidden(self):
        ownership.assert_document_owner(self.a, self.doc_a)
        with self.assertRaises(HTTPException) as caught:
            ownership.assert_document_owner(self.a, self.doc_b)
        self.assertEqual(caught.exception.status_code, 403)

    def test_an_unknown_document_is_not_found(self):
        with self.assertRaises(HTTPException) as caught:
            ownership.assert_document_owner(self.a, "no-such-document")
        self.assertEqual(caught.exception.status_code, 404)

    def test_another_actors_conversation_is_forbidden(self):
        conversation = create_conversation(
            "b chat", owner_type="guest", owner_id=self.b.actor_id
        )
        cid = conversation["conversation_id"]

        ownership.assert_conversation_owner(self.b, cid)
        with self.assertRaises(HTTPException) as caught:
            ownership.assert_conversation_owner(self.a, cid)
        self.assertEqual(caught.exception.status_code, 403)

    def test_an_unbound_conversation_id_is_allowed(self):
        # Creation binds it to the caller, so this must not raise.
        ownership.assert_conversation_owner(self.a, "conv-does-not-exist-yet")

    def test_retrieval_scope_drops_foreign_documents(self):
        self.assertEqual(
            ownership.visible_document_ids(self.a, [self.doc_a, self.doc_b]),
            [self.doc_a],
        )
        self.assertEqual(ownership.visible_document_ids(self.a, [self.doc_b]), [])
        self.assertEqual(ownership.visible_document_ids(self.a, None), [])

    def test_documents_predating_ownership_stay_shared(self):
        legacy = self.ready_document("legacy.pdf")
        self.assertTrue(ownership.owns_document(self.a, legacy))
        self.assertTrue(ownership.owns_document(self.b, legacy))
        self.assertEqual(
            ownership.visible_document_ids(self.a, [self.doc_a, legacy, self.doc_b]),
            [self.doc_a, legacy],
        )

    def test_each_actor_sees_only_their_own_library(self):
        from database.document_service import list_documents

        names = [
            doc["filename"]
            for doc in list_documents(owner_type="guest", owner_id=self.a.actor_id)
        ]
        self.assertEqual(names, ["a.pdf"])


class TestGuestMigration(TemporaryDatabase):
    def setUp(self):
        super().setUp()
        self.auth = patch.multiple(
            settings,
            AUTH_PROVIDER="supabase",
            SUPABASE_JWT_SECRET=JWT_SECRET,
            QUOTA_GUEST_MAX_QUESTIONS=3,
            QUOTA_USER_MAX_PDFS=5,
            QUOTA_USER_MAX_QUESTIONS_MONTHLY=100,
        )
        self.auth.start()
        self.addCleanup(self.auth.stop)

        self.session_id = "guest-session-migrate01"
        self.guest = resolve_context(None, self.session_id)
        self.document_id = self.ready_document("trial.pdf", "guest", self.session_id)
        self.conversation_id = create_conversation(
            "trial chat", owner_type="guest", owner_id=self.session_id
        )["conversation_id"]
        for _ in range(3):
            quotas.record_question(self.guest)

        self.user = resolve_context(
            f"Bearer {make_token('sub-new', 'new@example.com')}", self.session_id
        )

    def migrate(self) -> tuple[int, int]:
        session = get_guest_session(self.session_id)
        documents = reassign_documents(
            "guest", self.session_id, self.user.actor_type, self.user.actor_id
        )
        conversations = reassign_conversations(
            "guest", self.session_id, self.user.actor_type, self.user.actor_id
        )
        mark_guest_migrated(self.session_id, self.user.actor_id)
        for _ in range(int(session["question_count"])):
            quotas.record_question(self.user)
        return documents, conversations

    def test_signing_in_carries_over_the_pdf_and_the_chat(self):
        documents, conversations = self.migrate()
        self.assertEqual((documents, conversations), (1, 1))

        record = get_document(self.document_id)
        self.assertEqual(record["owner_type"], "user")
        self.assertEqual(record["owner_id"], self.user.actor_id)
        self.assertEqual(
            conversation_owner(self.conversation_id), ("user", self.user.actor_id)
        )
        ownership.assert_document_owner(self.user, self.document_id)
        ownership.assert_conversation_owner(self.user, self.conversation_id)

    def test_the_old_guest_session_loses_access(self):
        self.migrate()
        with self.assertRaises(HTTPException) as caught:
            ownership.assert_document_owner(self.guest, self.document_id)
        self.assertEqual(caught.exception.status_code, 403)

    def test_trial_questions_count_against_the_monthly_allowance(self):
        self.migrate()
        summary = quotas.usage_summary(self.user)
        self.assertEqual(summary["tier"], "free")
        self.assertEqual(summary["questions_used"], 3)
        self.assertEqual(summary["questions_limit"], 100)
        self.assertEqual(summary["pdfs_used"], 1)
        self.assertEqual(summary["pdfs_limit"], 5)

        # The exhausted guest can keep working as a signed-in user.
        quotas.check_question_allowed(self.user)
        quotas.check_upload_allowed(self.user)

    def test_a_trial_cannot_be_claimed_twice(self):
        self.migrate()
        session = get_guest_session(self.session_id)
        self.assertEqual(session["migrated_to_user_id"], self.user.actor_id)


if __name__ == "__main__":
    unittest.main()
