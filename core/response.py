from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    status: int
    message: str
    result: Optional[T] = None

def success_response(data: Any, message: str = "Success", status_code: int = 200) -> APIResponse[Any]:
    return APIResponse(
        status=status_code,
        message=message,
        result=data
    )
