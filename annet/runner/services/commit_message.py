import getpass


from annet.runner.protocols import CommitMessageSource


class SimpleCommitMessageSource(CommitMessageSource):
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message

    async def get_message(self) -> str:
        return self.user_message


class LocalUserCommitMessageSource(CommitMessageSource):
    def __init__(self, user_message: str) -> None:
        self.user_message = user_message

    async def get_message(self) -> str:
        user = getpass.getuser()
        email = f"{user}@localhost"
        message = self.user_message
        if message:
            message = f": {message}"
        return f"[annet]{email}{message}"
