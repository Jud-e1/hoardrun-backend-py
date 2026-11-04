"""
KYC (Know Your Customer) Service
Handles KYC verification via Persona (withpersona.com) API integration.
"""

import uuid
import hmac
import hashlib
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.kyc import (
    KYCDocumentUploadRequest,
    KYCUpdateRequest,
    FaceVerificationRequest,
    KYCStatusResponse,
    KYCRequirementsResponse,
    FaceVerificationResponse,
    KYCDocumentProfile,
    VerificationLevel,
    DocumentType,
    DocumentStatus,
    KYCStatus,
    RiskLevel,
    PersonalInformation,
    AddressInformation,
    EmploymentInformation,
)
from ..core.exceptions import ValidationError, NotFoundError, ConflictError
from ..repositories.mock_repository import MockRepository
from ..config.settings import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Persona API constants
# ---------------------------------------------------------------------------
PERSONA_BASE_URL = "https://withpersona.com/api/v1"
PERSONA_API_VERSION = "2023-01-05"


class PersonaClient:
    """Thin async wrapper around the Persona REST API."""

    def __init__(self, api_key: str, template_id: str, webhook_secret: str = ""):
        self.api_key = api_key
        self.template_id = template_id
        self.webhook_secret = webhook_secret
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Persona-Version": PERSONA_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Inquiries
    # ------------------------------------------------------------------

    async def create_inquiry(
        self,
        reference_id: str,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new Persona inquiry (verification session).

        Args:
            reference_id: Your internal user / KYC-profile ID so Persona can
                          correlate results back to your system.
            fields:       Optional pre-fill data (name, DOB, address …).

        Returns:
            Full Persona inquiry object.
        """
        payload: Dict[str, Any] = {
            "data": {
                "attributes": {
                    "inquiry-template-id": self.template_id,
                    "reference-id": reference_id,
                }
            }
        }

        if fields:
            payload["data"]["attributes"]["fields"] = fields

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{PERSONA_BASE_URL}/inquiries",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_inquiry(self, inquiry_id: str) -> Dict[str, Any]:
        """Fetch a single inquiry by its Persona ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{PERSONA_BASE_URL}/inquiries/{inquiry_id}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def resume_inquiry(self, inquiry_id: str) -> Dict[str, Any]:
        """
        Resume (re-open) an existing inquiry so the user can continue
        or redo steps.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{PERSONA_BASE_URL}/inquiries/{inquiry_id}/resume",
                headers=self._headers,
                json={},
            )
            response.raise_for_status()
            return response.json()

    async def approve_inquiry(self, inquiry_id: str) -> Dict[str, Any]:
        """Manually approve an inquiry (useful for sandbox testing)."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{PERSONA_BASE_URL}/inquiries/{inquiry_id}/approve",
                headers=self._headers,
                json={},
            )
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Verifications
    # ------------------------------------------------------------------

    async def list_verifications(self, inquiry_id: str) -> List[Dict[str, Any]]:
        """Return all verifications attached to an inquiry."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{PERSONA_BASE_URL}/verifications",
                headers=self._headers,
                params={"filter[inquiry-id]": inquiry_id},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    # ------------------------------------------------------------------
    # Webhook signature verification
    # ------------------------------------------------------------------

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """
        Validate the Persona-Signature header on incoming webhooks.

        Persona uses HMAC-SHA256:
          t=<timestamp>,v1=<hex-digest>
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured — skipping signature check")
            return True

        try:
            parts = dict(item.split("=", 1) for item in signature_header.split(","))
            timestamp = parts.get("t", "")
            v1_signature = parts.get("v1", "")

            signed_payload = f"{timestamp}.".encode() + raw_body
            expected = hmac.new(
                self.webhook_secret.encode(), signed_payload, hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected, v1_signature)
        except Exception as exc:
            logger.error(f"Webhook signature verification error: {exc}")
            return False


# ---------------------------------------------------------------------------
# Internal status mapping
# ---------------------------------------------------------------------------

# Persona inquiry statuses → our KYCStatus
_PERSONA_STATUS_MAP: Dict[str, KYCStatus] = {
    "created": KYCStatus.NOT_STARTED,
    "pending": KYCStatus.IN_PROGRESS,
    "needs_review": KYCStatus.PENDING_REVIEW,
    "approved": KYCStatus.APPROVED,
    "declined": KYCStatus.REJECTED,
    "expired": KYCStatus.EXPIRED,
    # legacy / edge cases
    "completed": KYCStatus.APPROVED,
    "failed": KYCStatus.REJECTED,
}

# Persona verification statuses  → our DocumentStatus
_VERIFICATION_STATUS_MAP: Dict[str, DocumentStatus] = {
    "passed": DocumentStatus.VERIFIED,
    "failed": DocumentStatus.REJECTED,
    "initiated": DocumentStatus.UPLOADED,
    "submitted": DocumentStatus.PROCESSING,
    "requires_retry": DocumentStatus.REJECTED,
    "confirmed": DocumentStatus.VERIFIED,
    "not_applicable": DocumentStatus.UPLOADED,
}


def _map_persona_status(persona_status: str) -> KYCStatus:
    return _PERSONA_STATUS_MAP.get(persona_status, KYCStatus.IN_PROGRESS)


def _map_verification_status(persona_status: str) -> DocumentStatus:
    return _VERIFICATION_STATUS_MAP.get(persona_status, DocumentStatus.UPLOADED)


# ---------------------------------------------------------------------------
# Main KYC Service
# ---------------------------------------------------------------------------


class KYCService:
    """
    KYC service backed by Persona for identity verification.

    Flow
    ----
    1. ``initiate_persona_inquiry`` — creates a Persona inquiry and persists
       the inquiry ID against the user's KYC profile.  The caller (router)
       should return the ``session-token`` to the frontend so it can render
       the Persona embedded flow.

    2. ``handle_persona_webhook`` — receives Persona webhook events and keeps
       the local KYC profile in sync (approved / declined / needs_review …).

    3. All existing public methods (get_kyc_status, upload_document, …) still
       work so the rest of the codebase doesn't need to change.
    """

    def __init__(self):
        self.repository = MockRepository()
        self.file_storage_path = "/tmp/kyc_documents"

        # Resolve Persona credentials from settings (add these to settings.py)
        persona_api_key: str = getattr(settings, "persona_api_key", "")
        persona_template_id: str = getattr(settings, "persona_template_id", "")
        persona_webhook_secret: str = getattr(settings, "persona_webhook_secret", "")

        if not persona_api_key or not persona_template_id:
            logger.warning(
                "Persona API key / template ID not configured. "
                "KYC will fall back to mock mode."
            )

        self.persona = PersonaClient(
            api_key=persona_api_key,
            template_id=persona_template_id,
            webhook_secret=persona_webhook_secret,
        )
        self._mock_mode = not (persona_api_key and persona_template_id)

        self._init_mock_data()

    # ------------------------------------------------------------------
    # Persona-specific public methods
    # ------------------------------------------------------------------

    async def initiate_persona_inquiry(
        self,
        user_id: str,
        db=None,
        prefill: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create (or resume) a Persona inquiry for the given user.

        Returns a dict with:
          - ``inquiry_id``    — Persona inquiry ID (store / display to user)
          - ``session_token`` — Short-lived token for the Persona embedded flow
          - ``status``        — Current inquiry status
        """
        # Load or create the KYC profile
        kyc_profile = self._find_kyc_profile(user_id)
        if not kyc_profile:
            kyc_profile = self._create_kyc_profile(user_id)

        existing_inquiry_id: Optional[str] = kyc_profile.get("persona_inquiry_id")

        if self._mock_mode:
            return self._mock_inquiry_response(user_id, existing_inquiry_id)

        try:
            if existing_inquiry_id:
                # Resume a previous session so the user can continue
                logger.info(f"Resuming Persona inquiry {existing_inquiry_id} for user {user_id}")
                result = await self.persona.resume_inquiry(existing_inquiry_id)
            else:
                # Build optional pre-fill from personal info already on file
                fields = prefill or self._build_persona_prefill(kyc_profile)
                logger.info(f"Creating Persona inquiry for user {user_id}")
                result = await self.persona.create_inquiry(
                    reference_id=user_id,
                    fields=fields,
                )

            inquiry = result.get("data", {})
            inquiry_id: str = inquiry.get("id", "")
            attributes: Dict[str, Any] = inquiry.get("attributes", {})
            session_token: str = attributes.get("session-token", "")
            persona_status: str = attributes.get("status", "created")

            # Persist inquiry ID and update status
            kyc_profile["persona_inquiry_id"] = inquiry_id
            kyc_profile["overall_status"] = _map_persona_status(persona_status)
            kyc_profile["updated_at"] = datetime.utcnow()
            self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

            logger.info(
                f"Persona inquiry {inquiry_id} initiated for user {user_id} "
                f"(status={persona_status})"
            )

            return {
                "inquiry_id": inquiry_id,
                "session_token": session_token,
                "status": persona_status,
                "kyc_status": kyc_profile["overall_status"],
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                f"Persona API error for user {user_id}: "
                f"{exc.response.status_code} {exc.response.text}"
            )
            raise ValidationError(f"Persona API error: {exc.response.text}") from exc

    async def sync_inquiry_from_persona(self, inquiry_id: str) -> Dict[str, Any]:
        """
        Pull the latest state of a Persona inquiry and update the local
        KYC profile.  Useful for polling / manual refresh.

        Returns the updated KYC status response dict.
        """
        if self._mock_mode:
            return {"status": "approved", "mock": True}

        try:
            result = await self.persona.get_inquiry(inquiry_id)
            return await self._apply_inquiry_result(result)
        except httpx.HTTPStatusError as exc:
            logger.error(f"Persona sync error for inquiry {inquiry_id}: {exc}")
            raise ValidationError(f"Persona sync error: {exc.response.text}") from exc

    async def handle_persona_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process an inbound Persona webhook event.

        Call this from your webhook router endpoint.  The router should:
          1. Read the raw bytes before parsing JSON.
          2. Pass both raw_body and the parsed payload here.

        Supported events
        ----------------
        - ``inquiry.approved``
        - ``inquiry.declined``
        - ``inquiry.needs_review``
        - ``inquiry.completed``
        - ``inquiry.expired``
        - ``verification.passed``
        - ``verification.failed``
        """
        # Verify signature
        if not self.persona.verify_webhook_signature(raw_body, signature_header):
            raise ValidationError("Invalid Persona webhook signature")

        event_name: str = payload.get("data", {}).get("attributes", {}).get("name", "")
        payload_type: str = payload.get("data", {}).get("type", "")

        logger.info(f"Received Persona webhook: {event_name or payload_type}")

        # ---- Inquiry-level events -------------------------------------------
        if "inquiry" in event_name:
            inquiry_data = (
                payload.get("data", {})
                .get("attributes", {})
                .get("payload", {})
                .get("data", {})
            )
            if not inquiry_data:
                # Some webhook shapes embed the inquiry directly
                inquiry_data = payload.get("data", {})

            return await self._apply_inquiry_result({"data": inquiry_data})

        # ---- Verification-level events (document / selfie checks) -----------
        if "verification" in event_name:
            verification_data = (
                payload.get("data", {})
                .get("attributes", {})
                .get("payload", {})
                .get("data", {})
            )
            await self._apply_verification_result(verification_data)
            return {"processed": True, "event": event_name}

        logger.debug(f"Unhandled Persona webhook event: {event_name}")
        return {"processed": False, "event": event_name}

    # ------------------------------------------------------------------
    # Existing public interface (unchanged signatures)
    # ------------------------------------------------------------------

    async def get_kyc_status(self, user_id: str) -> KYCStatusResponse:
        """Get comprehensive KYC status for user."""
        kyc_profile = self._find_kyc_profile(user_id)
        if not kyc_profile:
            kyc_profile = self._create_kyc_profile(user_id)

        user_documents = self._load_documents(user_id)

        verification_level = self._determine_verification_level(kyc_profile)
        risk_level = self._assess_risk_level(kyc_profile)
        completion_percentage = self._calculate_completion_percentage(kyc_profile)

        kyc_profile.update(
            {
                "verification_level": verification_level,
                "risk_level": risk_level,
                "updated_at": datetime.utcnow(),
            }
        )
        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

        required_documents = self._get_required_documents(verification_level)

        return KYCStatusResponse(
            user_id=user_id,
            overall_status=kyc_profile["overall_status"],
            verification_level=verification_level,
            risk_level=risk_level,
            completion_percentage=completion_percentage,
            required_documents=required_documents,
            submitted_documents=user_documents,
            personal_info_complete=bool(kyc_profile.get("personal_info")),
            address_verified=bool(kyc_profile.get("address_info")),
            identity_verified=any(
                d.status == DocumentStatus.VERIFIED for d in user_documents
            ),
            face_verified=bool(kyc_profile.get("last_face_verification")),
            last_updated=kyc_profile["updated_at"],
            next_review_date=kyc_profile.get("next_review_date"),
            restrictions=kyc_profile.get("restrictions", []),
        )

    async def upload_document(
        self,
        user_id: str,
        upload_request: KYCDocumentUploadRequest,
        file_content: bytes,
    ) -> KYCDocumentProfile:
        """Upload a KYC document (stored locally; Persona handles actual verification)."""
        existing_docs = [
            d
            for d in self.repository.data.get("kyc_documents", {}).values()
            if d["user_id"] == user_id
            and d["document_type"] == upload_request.document_type
        ]
        active_docs = [
            d
            for d in existing_docs
            if d["status"] not in [DocumentStatus.REJECTED, DocumentStatus.EXPIRED]
        ]
        if active_docs:
            raise ConflictError(
                f"Document of type {upload_request.document_type} already exists"
            )

        document_id = f"doc_{uuid.uuid4().hex[:8]}"
        file_extension = (
            upload_request.file_name.split(".")[-1]
            if "." in upload_request.file_name
            else "bin"
        )
        file_path = f"{self.file_storage_path}/{document_id}.{file_extension}"
        self._save_file(file_content, file_path)

        document_data: Dict[str, Any] = {
            "id": document_id,
            "user_id": user_id,
            "kyc_profile_id": f"kyc_{user_id}",
            "document_type": upload_request.document_type,
            "file_name": upload_request.file_name,
            "file_path": file_path,
            "file_size": upload_request.file_size,
            "mime_type": upload_request.mime_type,
            "status": DocumentStatus.UPLOADED,
            "upload_date": datetime.utcnow(),
            "verified_date": None,
            "expiry_date": None,
            "rejection_reason": None,
            "description": upload_request.description,
            "metadata": {},
        }
        self.repository.create("kyc_documents", document_id, document_data)
        await self._update_kyc_status_after_document_upload(user_id)

        return KYCDocumentProfile(
            id=document_data["id"],
            document_type=document_data["document_type"],
            file_name=document_data["file_name"],
            file_size=document_data["file_size"],
            mime_type=document_data["mime_type"],
            status=document_data["status"],
            upload_date=document_data["upload_date"],
            verified_date=document_data.get("verified_date"),
            expiry_date=document_data.get("expiry_date"),
            rejection_reason=document_data.get("rejection_reason"),
            description=document_data.get("description"),
        )

    async def perform_face_verification(
        self,
        user_id: str,
        verification_request: FaceVerificationRequest,
    ) -> FaceVerificationResponse:
        """
        Face verification is handled inside the Persona embedded flow.
        This method syncs the result from Persona if an inquiry exists,
        otherwise falls back to the legacy mock behaviour.
        """
        kyc_profile = self._find_kyc_profile(user_id)
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")

        if kyc_profile.get("face_verification_attempts", 0) >= 5:
            raise ConflictError("Maximum face verification attempts exceeded")

        inquiry_id = kyc_profile.get("persona_inquiry_id")
        if inquiry_id and not self._mock_mode:
            try:
                verifications = await self.persona.list_verifications(inquiry_id)
                selfie_checks = [
                    v
                    for v in verifications
                    if "selfie" in v.get("type", "").lower()
                    or "face" in v.get("type", "").lower()
                ]

                if selfie_checks:
                    latest = selfie_checks[-1]
                    attrs = latest.get("attributes", {})
                    persona_status = attrs.get("status", "initiated")
                    passed = persona_status == "passed"

                    confidence_score = float(
                        attrs.get("confidence", 0.95 if passed else 0.4)
                    )
                    liveness = attrs.get("checks", {}).get("liveness", {}).get("passed", passed)
                    doc_match = attrs.get("checks", {}).get("document-similarity", {}).get("passed", passed)

                    kyc_profile["last_face_verification"] = datetime.utcnow() if passed else None
                    kyc_profile["face_verification_attempts"] = (
                        kyc_profile.get("face_verification_attempts", 0) + 1
                    )
                    kyc_profile["updated_at"] = datetime.utcnow()
                    self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

                    return FaceVerificationResponse(
                        verification_id=latest.get("id", f"face_{uuid.uuid4().hex[:8]}"),
                        status="completed" if passed else "failed",
                        confidence_score=confidence_score,
                        liveness_check=bool(liveness),
                        document_match=bool(doc_match),
                        message="Face verification successful" if passed else "Face verification failed",
                        next_steps=[] if passed else [
                            "Ensure good lighting conditions",
                            "Remove sunglasses or face coverings",
                            "Look directly at the camera",
                        ],
                    )
            except Exception as exc:
                logger.warning(f"Could not fetch Persona face verifications: {exc}")

        # ---- Fallback mock -----------------------------------------------
        import random

        passed = random.random() < 0.8
        kyc_profile["last_face_verification"] = datetime.utcnow() if passed else None
        kyc_profile["face_verification_attempts"] = (
            kyc_profile.get("face_verification_attempts", 0) + 1
        )
        kyc_profile["updated_at"] = datetime.utcnow()
        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

        return FaceVerificationResponse(
            verification_id=f"face_{uuid.uuid4().hex[:8]}",
            status="completed" if passed else "failed",
            confidence_score=random.uniform(0.85, 0.99) if passed else random.uniform(0.3, 0.7),
            liveness_check=passed,
            document_match=passed,
            message="Face verification successful" if passed else "Face verification failed",
            next_steps=[] if passed else ["Ensure good lighting", "Look directly at camera"],
        )

    async def update_kyc_information(
        self,
        user_id: str,
        update_request: KYCUpdateRequest,
    ) -> KYCStatusResponse:
        """Update KYC information."""
        kyc_profile = self._find_kyc_profile(user_id)
        profile_id = kyc_profile["id"] if kyc_profile else None
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")

        if update_request.personal_info:
            kyc_profile["personal_info"] = update_request.personal_info.dict()
        if update_request.address_info:
            kyc_profile["address_info"] = update_request.address_info.dict()
        if update_request.employment_info:
            kyc_profile["employment_info"] = update_request.employment_info.dict()
        if update_request.phone_number:
            kyc_profile["phone_number"] = update_request.phone_number

        if kyc_profile["overall_status"] == KYCStatus.NOT_STARTED:
            kyc_profile["overall_status"] = KYCStatus.IN_PROGRESS
        kyc_profile["updated_at"] = datetime.utcnow()

        self.repository.update("kyc_profiles", profile_id, kyc_profile)
        return await self.get_kyc_status(user_id)

    async def get_kyc_requirements(
        self,
        user_id: str,
        verification_level: Optional[VerificationLevel] = None,
    ) -> KYCRequirementsResponse:
        """Get KYC requirements for a verification level."""
        if not verification_level:
            verification_level = VerificationLevel.STANDARD

        requirements_map = {
            VerificationLevel.BASIC: {
                "required_documents": [
                    {"type": "email_verification", "name": "Email Verification", "required": True},
                    {"type": "phone_verification", "name": "Phone Verification", "required": True},
                ],
                "required_information": ["email", "phone_number"],
                "estimated_time": "5 minutes",
                "benefits": ["Basic account access", "Limited transactions ($100/day)"],
                "transaction_limits": {"daily_limit": 100, "monthly_limit": 1000, "currency": "USD"},
            },
            VerificationLevel.STANDARD: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "personal_info", "name": "Personal Information", "required": True},
                    {"type": "persona_flow", "name": "Persona Identity Verification", "required": True},
                ],
                "required_information": ["first_name", "last_name", "date_of_birth", "nationality"],
                "estimated_time": "10–15 minutes",
                "benefits": [
                    "Increased transaction limits ($1,000/day)",
                    "Access to savings features",
                    "Mobile money integration",
                ],
                "transaction_limits": {"daily_limit": 1000, "monthly_limit": 10000, "currency": "USD"},
            },
            VerificationLevel.ENHANCED: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "proof_of_address", "name": "Proof of Address", "required": True},
                    {"type": "persona_flow", "name": "Persona Identity + Face Verification", "required": True},
                ],
                "required_information": ["personal_info", "address_info", "face_verification"],
                "estimated_time": "20–30 minutes",
                "benefits": [
                    "High transaction limits ($5,000/day)",
                    "Investment features",
                    "International transfers",
                    "Premium support",
                ],
                "transaction_limits": {"daily_limit": 5000, "monthly_limit": 50000, "currency": "USD"},
            },
            VerificationLevel.PREMIUM: {
                "required_documents": [
                    {"type": "national_id", "name": "National ID", "required": True},
                    {"type": "proof_of_address", "name": "Proof of Address", "required": True},
                    {"type": "proof_of_income", "name": "Proof of Income", "required": True},
                    {"type": "persona_flow", "name": "Full Persona KYC Flow", "required": True},
                ],
                "required_information": ["personal_info", "address_info", "employment_info", "face_verification"],
                "estimated_time": "30–45 minutes",
                "benefits": [
                    "Unlimited transaction limits",
                    "Advanced investment options",
                    "Business account features",
                    "Dedicated account manager",
                    "Priority processing",
                ],
                "transaction_limits": {"daily_limit": "unlimited", "monthly_limit": "unlimited", "currency": "USD"},
            },
        }

        requirements = requirements_map.get(verification_level)
        if not requirements:
            raise ValidationError(f"Invalid verification level: {verification_level}")

        return KYCRequirementsResponse(
            verification_level=verification_level,
            required_documents=requirements["required_documents"],
            required_information=requirements["required_information"],
            estimated_time=requirements["estimated_time"],
            benefits=requirements["benefits"],
            transaction_limits=requirements["transaction_limits"],
        )

    async def get_user_documents(
        self,
        user_id: str,
        document_type: Optional[DocumentType] = None,
    ) -> List[KYCDocumentProfile]:
        """Get user KYC documents."""
        docs = self._load_documents(user_id)
        if document_type:
            docs = [d for d in docs if d.document_type == document_type]
        docs.sort(key=lambda x: x.upload_date, reverse=True)
        return docs

    async def delete_document(self, user_id: str, document_id: str) -> None:
        """Delete a KYC document."""
        import os

        document_data = self.repository.get("kyc_documents", document_id)
        if not document_data or document_data["user_id"] != user_id:
            raise NotFoundError("Document not found")
        if document_data["status"] == DocumentStatus.VERIFIED:
            raise ConflictError("Cannot delete verified document")
        try:
            if os.path.exists(document_data["file_path"]):
                os.remove(document_data["file_path"])
        except Exception:
            pass
        self.repository.delete("kyc_documents", document_id)

    async def submit_for_review(self, user_id: str) -> KYCStatusResponse:
        """Submit KYC for manual review."""
        current_status = await self.get_kyc_status(user_id)

        if current_status.completion_percentage < 80:
            raise ValidationError(
                "KYC information is incomplete. Please complete all required fields."
            )
        if not current_status.identity_verified:
            raise ValidationError(
                "Identity verification required. Please upload and verify your ID document."
            )

        kyc_profile = self._find_kyc_profile(user_id)
        if not kyc_profile:
            raise NotFoundError("KYC profile not found")

        kyc_profile.update(
            {
                "overall_status": KYCStatus.PENDING_REVIEW,
                "updated_at": datetime.utcnow(),
                "next_review_date": datetime.utcnow() + timedelta(days=3),
            }
        )
        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)
        return await self.get_kyc_status(user_id)

    async def get_verification_levels(self) -> List[Dict[str, Any]]:
        """Return all available verification levels with their requirements."""
        levels = []
        for level in VerificationLevel:
            requirements = await self.get_kyc_requirements("_dummy", level)
            levels.append(
                {"level": level.value, "name": level.value.title(), "requirements": requirements.dict()}
            )
        return levels

    async def health_check(self) -> Dict[str, Any]:
        """Health check for KYC service."""
        total_profiles = len(self.repository.data.get("kyc_profiles", {}))
        total_documents = len(self.repository.data.get("kyc_documents", {}))
        status_counts: Dict[str, int] = {}
        for profile_data in self.repository.data.get("kyc_profiles", {}).values():
            s = str(profile_data["overall_status"])
            status_counts[s] = status_counts.get(s, 0) + 1

        persona_status = "not_configured"
        if not self._mock_mode:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(
                        f"{PERSONA_BASE_URL}/api/v1/inquiry-templates",
                        headers=self.persona._headers,
                    )
                    persona_status = "reachable" if resp.status_code < 500 else "error"
            except Exception:
                persona_status = "unreachable"

        return {
            "service": "kyc",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "persona": {
                "mode": "mock" if self._mock_mode else "live",
                "api_status": persona_status,
            },
            "statistics": {
                "total_profiles": total_profiles,
                "total_documents": total_documents,
                "status_distribution": status_counts,
            },
        }

    # ------------------------------------------------------------------
    # Private helpers — Persona integration
    # ------------------------------------------------------------------

    async def _apply_inquiry_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Persona inquiry payload and update the corresponding
        local KYC profile.
        """
        inquiry = result.get("data", {})
        inquiry_id: str = inquiry.get("id", "")
        attributes: Dict[str, Any] = inquiry.get("attributes", {})
        persona_status: str = attributes.get("status", "pending")
        reference_id: str = attributes.get("reference-id", "")

        # Locate the profile by reference-id (= user_id) or stored inquiry_id
        kyc_profile = None
        if reference_id:
            kyc_profile = self._find_kyc_profile(reference_id)
        if not kyc_profile and inquiry_id:
            for p in self.repository.data.get("kyc_profiles", {}).values():
                if p.get("persona_inquiry_id") == inquiry_id:
                    kyc_profile = p
                    break

        if not kyc_profile:
            logger.warning(
                f"No KYC profile found for Persona inquiry {inquiry_id} / ref {reference_id}"
            )
            return {"processed": False, "reason": "profile_not_found"}

        new_status = _map_persona_status(persona_status)
        kyc_profile["overall_status"] = new_status
        kyc_profile["persona_inquiry_id"] = inquiry_id
        kyc_profile["updated_at"] = datetime.utcnow()

        # Pull name / DOB fields if Persona returns them
        fields: Dict[str, Any] = attributes.get("fields", {})
        if fields and not kyc_profile.get("personal_info"):
            kyc_profile["personal_info"] = {
                "first_name": fields.get("name-first", {}).get("value"),
                "last_name": fields.get("name-last", {}).get("value"),
                "date_of_birth": fields.get("birthdate", {}).get("value"),
                "nationality": fields.get("country-code", {}).get("value"),
            }

        if new_status == KYCStatus.APPROVED:
            kyc_profile["reviewed_at"] = datetime.utcnow()

        self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

        logger.info(
            f"Applied Persona inquiry result: inquiry={inquiry_id}, "
            f"user={kyc_profile.get('user_id')}, status={new_status}"
        )

        return {
            "processed": True,
            "inquiry_id": inquiry_id,
            "user_id": kyc_profile.get("user_id"),
            "kyc_status": str(new_status.value),
        }

    async def _apply_verification_result(self, verification: Dict[str, Any]) -> None:
        """Update a document record when a Persona verification event arrives."""
        v_id: str = verification.get("id", "")
        v_type: str = verification.get("type", "")
        attrs: Dict[str, Any] = verification.get("attributes", {})
        persona_status: str = attrs.get("status", "initiated")
        new_doc_status = _map_verification_status(persona_status)

        # Try to find a matching local document by metadata
        for doc_id, doc_data in self.repository.data.get("kyc_documents", {}).items():
            if doc_data.get("metadata", {}).get("persona_verification_id") == v_id:
                doc_data["status"] = new_doc_status
                if new_doc_status == DocumentStatus.VERIFIED:
                    doc_data["verified_date"] = datetime.utcnow()
                self.repository.update("kyc_documents", doc_id, doc_data)
                logger.info(f"Updated document {doc_id} status to {new_doc_status}")
                return

        logger.debug(f"No local document matched Persona verification {v_id} ({v_type})")

    def _build_persona_prefill(self, kyc_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Convert stored personal info into Persona field format."""
        personal_info: Dict[str, Any] = kyc_profile.get("personal_info") or {}
        fields: Dict[str, Any] = {}

        if personal_info.get("first_name"):
            fields["name-first"] = personal_info["first_name"]
        if personal_info.get("last_name"):
            fields["name-last"] = personal_info["last_name"]
        if personal_info.get("date_of_birth"):
            fields["birthdate"] = personal_info["date_of_birth"]
        if personal_info.get("nationality"):
            fields["country-code"] = personal_info["nationality"]

        return fields

    def _mock_inquiry_response(
        self, user_id: str, existing_inquiry_id: Optional[str]
    ) -> Dict[str, Any]:
        """Return a plausible mock response when Persona is not configured."""
        inquiry_id = existing_inquiry_id or f"inq_mock_{uuid.uuid4().hex[:12]}"

        # Persist the inquiry_id on the profile so subsequent calls resume it
        if not existing_inquiry_id:
            kyc_profile = self._find_kyc_profile(user_id)
            if kyc_profile:
                kyc_profile["persona_inquiry_id"] = inquiry_id
                kyc_profile["overall_status"] = KYCStatus.IN_PROGRESS
                self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

        return {
            "inquiry_id": inquiry_id,
            "session_token": f"mock_session_{uuid.uuid4().hex}",
            "status": "pending",
            "kyc_status": KYCStatus.IN_PROGRESS.value,
            "mock": True,
        }

    # ------------------------------------------------------------------
    # Private helpers — data layer
    # ------------------------------------------------------------------

    def _find_kyc_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        for profile_data in self.repository.data.get("kyc_profiles", {}).values():
            if profile_data["user_id"] == user_id:
                return profile_data
        return None

    def _create_kyc_profile(self, user_id: str) -> Dict[str, Any]:
        kyc_profile: Dict[str, Any] = {
            "id": f"kyc_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "overall_status": KYCStatus.NOT_STARTED,
            "verification_level": VerificationLevel.BASIC,
            "risk_level": RiskLevel.LOW,
            "personal_info": None,
            "address_info": None,
            "employment_info": None,
            "phone_number": None,
            "documents": [],
            "verification_history": [],
            "face_verification_attempts": 0,
            "last_face_verification": None,
            "restrictions": [],
            "persona_inquiry_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "reviewed_at": None,
            "reviewed_by": None,
            "next_review_date": None,
        }
        self.repository.create("kyc_profiles", kyc_profile["id"], kyc_profile)
        return kyc_profile

    def _load_documents(self, user_id: str) -> List[KYCDocumentProfile]:
        docs = []
        for doc_data in self.repository.data.get("kyc_documents", {}).values():
            if doc_data["user_id"] == user_id:
                docs.append(
                    KYCDocumentProfile(
                        id=doc_data["id"],
                        document_type=doc_data["document_type"],
                        file_name=doc_data["file_name"],
                        file_size=doc_data["file_size"],
                        mime_type=doc_data["mime_type"],
                        status=doc_data["status"],
                        upload_date=doc_data["upload_date"],
                        verified_date=doc_data.get("verified_date"),
                        expiry_date=doc_data.get("expiry_date"),
                        rejection_reason=doc_data.get("rejection_reason"),
                        description=doc_data.get("description"),
                    )
                )
        return docs

    def _save_file(self, file_content: bytes, file_path: str) -> None:
        import os

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_content)

    def _calculate_completion_percentage(self, kyc_profile: Dict[str, Any]) -> float:
        total_steps = 5
        completed = sum(
            [
                bool(kyc_profile.get("personal_info")),
                bool(kyc_profile.get("address_info")),
                bool(kyc_profile.get("employment_info")),
                any(
                    d.get("status") == DocumentStatus.VERIFIED
                    for d in kyc_profile.get("documents", [])
                ),
                bool(kyc_profile.get("last_face_verification")),
            ]
        )
        return (completed / total_steps) * 100

    def _determine_verification_level(
        self, kyc_profile: Dict[str, Any]
    ) -> VerificationLevel:
        has_personal = bool(kyc_profile.get("personal_info"))
        has_address = bool(kyc_profile.get("address_info"))
        has_employment = bool(kyc_profile.get("employment_info"))
        has_verified_docs = any(
            d.get("status") == DocumentStatus.VERIFIED
            for d in kyc_profile.get("documents", [])
        )
        has_face = bool(kyc_profile.get("last_face_verification"))

        if has_employment and has_verified_docs and has_face and has_address:
            return VerificationLevel.PREMIUM
        if has_address and has_verified_docs and has_face:
            return VerificationLevel.ENHANCED
        if has_verified_docs and has_personal:
            return VerificationLevel.STANDARD
        return VerificationLevel.BASIC

    def _assess_risk_level(self, kyc_profile: Dict[str, Any]) -> RiskLevel:
        risk_factors = 0
        emp = kyc_profile.get("employment_info") or {}
        if emp.get("employment_status") == "unemployed":
            risk_factors += 1
        if (emp.get("monthly_income") or 0) > 10000:
            risk_factors += 1
        rejected = sum(
            1
            for d in kyc_profile.get("documents", [])
            if d.get("status") == DocumentStatus.REJECTED
        )
        if rejected > 2:
            risk_factors += 2
        if kyc_profile.get("face_verification_attempts", 0) > 3:
            risk_factors += 1
        if risk_factors >= 3:
            return RiskLevel.HIGH
        if risk_factors >= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _get_required_documents(
        self, verification_level: VerificationLevel
    ) -> List[DocumentType]:
        return {
            VerificationLevel.BASIC: [],
            VerificationLevel.STANDARD: [DocumentType.NATIONAL_ID],
            VerificationLevel.ENHANCED: [
                DocumentType.NATIONAL_ID,
                DocumentType.PROOF_OF_ADDRESS,
            ],
            VerificationLevel.PREMIUM: [
                DocumentType.NATIONAL_ID,
                DocumentType.PROOF_OF_ADDRESS,
                DocumentType.PROOF_OF_INCOME,
            ],
        }.get(verification_level, [])

    async def _update_kyc_status_after_document_upload(self, user_id: str) -> None:
        kyc_profile = self._find_kyc_profile(user_id)
        if kyc_profile and kyc_profile["overall_status"] == KYCStatus.NOT_STARTED:
            kyc_profile["overall_status"] = KYCStatus.IN_PROGRESS
            kyc_profile["updated_at"] = datetime.utcnow()
            self.repository.update("kyc_profiles", kyc_profile["id"], kyc_profile)

    # ------------------------------------------------------------------
    # Seed data (kept from original for dev convenience)
    # ------------------------------------------------------------------

    def _init_mock_data(self) -> None:
        mock_profile = {
            "id": "kyc_001",
            "user_id": "user_001",
            "overall_status": KYCStatus.IN_PROGRESS,
            "verification_level": VerificationLevel.BASIC,
            "risk_level": RiskLevel.LOW,
            "personal_info": {
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "1990-01-15",
                "nationality": "UG",
                "gender": "male",
            },
            "address_info": None,
            "employment_info": None,
            "phone_number": "+256701234567",
            "documents": [],
            "verification_history": [],
            "face_verification_attempts": 0,
            "last_face_verification": None,
            "restrictions": [],
            "persona_inquiry_id": None,
            "created_at": datetime.utcnow() - timedelta(days=10),
            "updated_at": datetime.utcnow() - timedelta(days=2),
            "reviewed_at": None,
            "reviewed_by": None,
            "next_review_date": None,
        }
        self.repository.data.setdefault("kyc_profiles", {})["kyc_001"] = mock_profile

        mock_document = {
            "id": "doc_001",
            "user_id": "user_001",
            "kyc_profile_id": "kyc_001",
            "document_type": DocumentType.NATIONAL_ID,
            "file_name": "national_id.jpg",
            "file_path": "/tmp/kyc_documents/doc_001.jpg",
            "file_size": 1024000,
            "mime_type": "image/jpeg",
            "status": DocumentStatus.UPLOADED,
            "upload_date": datetime.utcnow() - timedelta(days=5),
            "verified_date": None,
            "expiry_date": None,
            "rejection_reason": None,
            "description": "National ID front page",
            "metadata": {},
        }
        self.repository.data.setdefault("kyc_documents", {})["doc_001"] = mock_document