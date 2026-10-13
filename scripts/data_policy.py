from enum import Enum


class DataClassification(str, Enum):
    SAMPLE = "sample"
    PUBLIC = "public"
    PRIVATE = "private"
def ensure_hosted_upload_allowed(classification: DataClassification | str) -> None:
    """Allow only sample or explicitly public data into hosted services."""
    try:
        classification = DataClassification(classification)
    except ValueError as error:
        raise ValueError(f"Unknown data classification: {classification!r}") from error
    if classification is DataClassification.PRIVATE:
        raise PermissionError("Private data cannot be uploaded to a hosted service")
