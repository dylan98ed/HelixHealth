from itertools import count


class UserFactory:
    """Small callable factory for persisted Django users."""

    def __init__(self, user_model):
        self.user_model = user_model
        self._sequence = count(1)

    def __call__(self, **attributes):
        sequence = next(self._sequence)
        username = attributes.setdefault(
            "username",
            f"foundation-user-{sequence}",
        )
        attributes.setdefault("email", f"{username}@example.test")
        attributes.setdefault("password", "foundation-test-password")
        return self.user_model.objects.create_user(**attributes)
