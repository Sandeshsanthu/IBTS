# filename: models.py

from pydantic import BaseModel


class CheckRequest(BaseModel):
    transactionRefId: str


class CompleteRequest(BaseModel):
    transactionId: str
    finalStatus: str
    responsePayload: str | None = None


class CheckResponse(BaseModel):
    duplicate: bool
    status: str
    transactionId: str
    responsePayload: str | None = None


