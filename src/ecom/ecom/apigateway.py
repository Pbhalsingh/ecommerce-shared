import json
from typing import Dict,Union,Optional
from .helpers import Encoder

__all__ = []


def cognito_user_id(event:dict) -> Optional[str]:

    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (TypeError,KeyError):
        return None

def iam_user_id(event:dict) -> Optional[str]:

    try:
        return event["requestContext"]["identity"]["userArn"]
    except (TypeError,KeyError):
        return None


def response(
    msg : Union[dict,str],
    status_code : int = 200,
    allow_origin:str = "*",
    allow_headers :str = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-requested-with",
    allow_methods :str= "GET,POST,PUT,DELETE,OPTIONS"
) -> Dict[str,Union[int,str]] :

    return {

        "statusCode" : status_code,
        "headers":{
            "Access-Control-Allow-Headers": allow_headers,
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": allow_methods
        },
        "body": json.dumps(msg,cls=Encoder)



    }



    