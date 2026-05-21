from internal_static_files.models import ShareMode
from internal_static_files.sharing import can_read_file


def test_owner_can_read_private_specific_file(file_factory, user_factory) -> None:
    owner = user_factory(email="owner@example.com")
    stored_file = file_factory(owner=owner, share_mode=ShareMode.SPECIFIC_PEOPLE)

    assert can_read_file(owner, stored_file)


def test_public_file_allows_any_authenticated_user(file_factory, user_factory) -> None:
    owner = user_factory(email="owner@example.com")
    requester = user_factory(email="reader@other.com")
    stored_file = file_factory(owner=owner, share_mode=ShareMode.PUBLIC)

    assert can_read_file(requester, stored_file)


def test_internal_file_allows_same_owner_domain(file_factory, user_factory) -> None:
    owner = user_factory(email="owner@example.com")
    requester = user_factory(email="reader@example.com")
    stored_file = file_factory(owner=owner, share_mode=ShareMode.INTERNAL)

    assert can_read_file(requester, stored_file)


def test_specific_people_allows_matching_recipient_email(file_factory, user_factory, share_factory) -> None:
    owner = user_factory(email="owner@example.com")
    requester = user_factory(email="reader@other.com")
    stored_file = file_factory(owner=owner, share_mode=ShareMode.SPECIFIC_PEOPLE)
    share_factory(stored_file, "Reader@Other.com")

    assert can_read_file(requester, stored_file)


def test_internal_file_denies_different_domain(file_factory, user_factory) -> None:
    owner = user_factory(email="owner@example.com")
    requester = user_factory(email="reader@other.com")
    stored_file = file_factory(owner=owner, share_mode=ShareMode.INTERNAL)

    assert not can_read_file(requester, stored_file)
