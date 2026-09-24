from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Identity:
    """Validated issuer and subject identity from an authentication provider."""

    issuer: str
    subject: str
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.issuer or not self.subject:
            raise ValueError("identity issuer and subject must not be blank")
