class Recovery:
    """Return a structured recovery decision without executing the retry."""

    RETRYABLE_ERRORS = (
        TimeoutError,
        ConnectionError,
    )

    def recover(self, error):
        error_type = type(error).__name__
        message = str(error)

        if isinstance(error, self.RETRYABLE_ERRORS):
            return {
                "action": "retry",
                "retryable": True,
                "reason": "transient_error",
                "error_type": error_type,
                "error": message,
            }

        return {
            "action": "fail",
            "retryable": False,
            "reason": "non_retryable_error",
            "error_type": error_type,
            "error": message,
        }
