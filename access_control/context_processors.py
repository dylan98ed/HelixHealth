from django.http import HttpRequest

from access_control.actors import actor_context_from_user
from access_control.policies import ADMINISTRATIVE_POLICY


def actor_roles(request: HttpRequest) -> dict[str, bool]:
    """Expose role checks needed by the shared template shell."""
    actor = actor_context_from_user(request.user)
    return {"is_administrative_actor": ADMINISTRATIVE_POLICY.allows(actor)}
