"""Constants for the uploads domain."""


class UploadStatusName:
    """
    Constants for UploadStatus model name field values.

    The UploadStatus model is a database-backed status table (not a Python enum).
    These constants prevent hardcoded status name strings throughout the codebase.
    """

    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
