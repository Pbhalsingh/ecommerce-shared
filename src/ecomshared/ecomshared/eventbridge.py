"""
EventBridge helpers for Lambda functions
"""
import os
from datetime import datetime
import json,jsonschema
from boto3.dynamodb.types import TypeDeserializer
from .helpers import Encoder



__all__ = ["ddb_to_event"]
deserialize = TypeDeserializer().deserialize

VALID_EVENT_TYPE = {
    #Inventory
    "InventoryCreateRequest" : "InventoryCreateRequest" ,
    "InventoryUpdateRequest" :  "InventoryUpdateRequest",
    "InventoryUpdateResponse" : "InventoryUpdateResponse",
    "RequisitionItemRequest" : "RequisitionItemRequest",
    "RequisitionItemRelease":"RequisitionItemRelease",
    "RequisitionStatusUpdate" : "RequisitionStatusUpdate",
    "ValidateInventoryItemRequest" : "ValidateInventoryItemRequest",
    "ValidateInventoryItemResponse":"ValidateInventoryItemResponse",
    "GetInventoryRequest":"GetInventoryRequest",
    "GetInventoryResponse" : "GetInventoryResponse",

    #Products
    "GetProductRequest" : "GetProductRequest" ,
    "GetProductResponse" : "GetProductResponse",

    #Orders 
    "OrderCreateRequest" : "OrderCreateRequest",
    "GetOrderRequest" : "GetOrderRequest",
    "GetOrderResponse" : "GetOrderResponse",
    "ValidateOrderRequest" : "ValidateOrderRequest",
    "VaildateOrderResponse" : "VaildateOrderResponse" ,

    #Delivery
    "ScheduledOrderItem" : "ScheduledOrderItem",
    "PackagingStatusUpdate" : "PackagingStatusUpdate",
    "TrackingGenerateRequest" : "TrackingGenerateRequest",
    "TrackingGenerateResponse" : "TrackingGenerateResponse",
    "PackageShipped" : "PackageShipped",

    #Invoice & Payment
    "InvoiceGenerateRequest" : "InvoiceGenerateRequest",
    "InvoiceGenerateResponse" : "InvoiceGenerateResponse",

    "PaymentProcessRequest" : "PaymentProcessRequest",
    "PaymentProcessResponse" : "PaymentProcessResponse"
}




def ddb_to_event(
        ddb_record: dict,
        event_bus_name: str,
        source: str,
        object_type: str,
        resource_key: str
    ) -> dict:
    """
    Transforms a DynamoDB Streams record into an EventBridge event

    For this function to works, you need to have a StreamViewType of
    NEW_AND_OLD_IMAGES.
    """

    event = {
        "Time": datetime.now(),
        "Source": source,
        "Resources": [
            str(deserialize(ddb_record["dynamodb"]["Keys"][resource_key]))
        ],
        "EventBusName": event_bus_name
    }

    # Created event
    if ddb_record["eventName"].upper() == "INSERT":
        event["DetailType"] = "{}Created".format(object_type)
        event["Detail"] = json.dumps({
            k: deserialize(v)
            for k, v
            in ddb_record["dynamodb"]["NewImage"].items()
        }, cls=Encoder)

    # Deleted event
    elif ddb_record["eventName"].upper() == "REMOVE":
        event["DetailType"] = "{}Deleted".format(object_type)
        event["Detail"] = json.dumps({
            k: deserialize(v)
            for k, v
            in ddb_record["dynamodb"]["OldImage"].items()
        }, cls=Encoder)

    elif ddb_record["eventName"].upper() == "MODIFY":
        new = {
            k: deserialize(v)
            for k, v
            in ddb_record["dynamodb"]["NewImage"].items()
        }
        old = {
            k: deserialize(v)
            for k, v
            in ddb_record["dynamodb"]["OldImage"].items()
        }

        # Old keys not in NewImage
        changed = [k for k in old.keys() if k not in new.keys()]
        for k in new.keys():
            # New keys not in OldImage
            if k not in old.keys():
                changed.append(k)
            # New keys that are not equal to old values
            elif new[k] != old[k]:
                changed.append(k)

        event["DetailType"] = "{}Modified".format(object_type)
        event["Detail"] = json.dumps({
            "new": new,
            "old": old,
            "changed": changed
        }, cls=Encoder)

    else:
        raise ValueError("Wrong eventName value for DynamoDB event: {}".format(ddb_record["eventName"]))

    return event


def create_event( type:str,
                  detail:dict,
                  bus_name:str,
                  source:str) ->  dict:

    
    if type not in VALID_EVENT_TYPE :
        raise Exception("Invalid event type {}".format(type))

    validate_event(type,detail)
  
    """ create Event Bridge event from input """
    event_bridge_event = {
        "Time" : datetime.now(),
        "Source" : "ecommerce.{}".format(source),
        "Resources" : [],
        "DetailType" : type,
        "Detail" : json.dumps(detail,cls=Encoder),
        "EventBusName" :   bus_name      
    }

    # pdb.set_trace()
    return event_bridge_event

def validate_event(eventType , detail):

    SCHEMA_FILE = os.path.join(os.path.dirname(__file__),"data/{}.json".format(eventType))

    with open(SCHEMA_FILE) as fs:
        schema =  json.load(fs)

    jsonschema.validate(detail,schema)

