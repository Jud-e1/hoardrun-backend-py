"""
DEPRECATED: ai_guidance.py has been merged into financial_insights.py.

Routes are now served from /insights/ai-guidance/* by the router in
app.api.v1.financial_insights. This shim re-exports the router for
backward compatibility with any include_router() references.
"""
from app.api.v1.financial_insights import router  # noqa: F401
