def test_user_factory_persists_unique_users(user_factory, postgresql_db):
    first_user = user_factory()
    second_user = user_factory(first_name="Ada")

    assert first_user.pk is not None
    assert second_user.pk is not None
    assert first_user.username != second_user.username
    assert second_user.first_name == "Ada"
    assert postgresql_db.vendor == "postgresql"
