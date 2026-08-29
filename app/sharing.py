from app.models import ShareMode, StoredFile, User, normalize_email


def can_read_file(requester: User, stored_file: StoredFile) -> bool:
    if requester.id == stored_file.owner_id:
        return True
    if stored_file.share_mode == ShareMode.PUBLIC:
        return True
    if stored_file.share_mode == ShareMode.INTERNAL:
        return requester.email_domain == stored_file.owner.email_domain
    if stored_file.share_mode == ShareMode.SPECIFIC_PEOPLE:
        requester_email = normalize_email(requester.email)
        return any(share.recipient_email == requester_email for share in stored_file.shares)
    return False
