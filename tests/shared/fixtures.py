import datetime
import os
import random
import string
import time
from typing import List, Optional
from urllib.parse import urlparse
import uuid
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
import boto3
import pytest
from .helpers import getParameter
from boto3.dynamodb.conditions import Key,Attr



sqs = boto3.client("sqs")
ssm = boto3.client("ssm")
warehouse_table = getParameter("/ecommerce/{}/warehouse/table/name".format("test"))
product_table = getParameter("/ecommerce/{}/products/table/name".format("test"))
REQ_QTY = 10


@pytest.fixture
def listener(request):
    """
    Listens to messages in the Listener queue for a given service for a fixed
    period of time.

    To use in your integration tests:

        from fixtures import listener

    Then to write a test:

        test_with_listener(listener):
            # Trigger an event that would result in messages
            # ...

            messages = listener("your-service")

            # Parse messages
    """

    def _listener(service_name: str, timeout: int=15):
        queue_url = ssm.get_parameter(
            Name="/ecommerce/{}/{}/listener/url".format(
                os.environ["ENVIRONMENT"], service_name
            )
        )["Parameter"]["Value"]

        print("queue_url", queue_url)
        messages = []
        start_time = time.time()
        while time.time() < start_time + timeout:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=min(20, int(time.time()-start_time+timeout))
            )
            if response.get("Messages", []):
                sqs.delete_message_batch(
                    QueueUrl=queue_url,
                    Entries=[
                        {"Id": m["MessageId"], "ReceiptHandle": m["ReceiptHandle"]}
                        for m in response["Messages"]
                    ]
                )
            messages.extend(response.get("Messages", []))

        return messages
    
    return _listener


@pytest.fixture
def iam_auth():
    """
    Helper function to return auth for IAM
    """

    def _iam_auth(endpoint):
        url = urlparse(endpoint)
        region = boto3.session.Session().region_name

        return BotoAWSRequestsAuth(
            aws_host=url.netloc,
            aws_region=region,
            aws_service="execute-api"
        )

    return _iam_auth


@pytest.fixture(scope="module")
def get_order(get_product):
    """
    Returns a random order generator function based on
    shared/resources/schemas.yaml

    Usage:

        from fixtures import get_order
        order = get_order()
    """

    def _get_order(
            order_id: Optional[str] = None,
            user_id: Optional[str] = None,
            products: Optional[List[dict]] = None,
            address: Optional[dict] = None
        ):
        now = datetime.datetime.now()

        order = {
            "orderId": order_id or str(uuid.uuid4()),
            "userId": user_id or str(uuid.uuid4()),
            "createdDate": now.isoformat(),
            "modifiedDate": now.isoformat(),
            "status": "NEW",
            "products": products or [
                get_product() for _ in range(random.randrange(2, 8))
            ],
            "address": address or {
                "name": "Parth Urvi",
                "streetAddress": "{} Test St".format(random.randint(10, 100)),
                "postCode": str((random.randrange(10**4, 10**5))),
                "city": "Test City",
                "state": "Test State",
                "country": "".join(random.choices(string.ascii_uppercase, k=2)),
                "phoneNumber": "+{}".format(random.randrange(10**9, 10**10))
            },
            "paymentDetail": {
                "name" : "Prashant Test",
                "cardNumber"  : 41111,
                "expDate" : "4/22",
                "cvc" : 100
            },
            "deliveryPrice": random.randint(0, 50)
        }

        # Insert products quantities and calculate total cost of the order
        total = order["deliveryPrice"]
        for product in order["products"]:
            product["quantity"] = random.randrange(1, 10)
            total += product["quantity"] * product["price"]
        order["total"] = total

        return order

    return _get_order


@pytest.fixture(scope="module")
def get_product():
    """
    Returns a random product generator function based on
    shared/resources/schemas.yaml

    Usage:

       from fixtures import get_product
       product = get_product()
    """

    PRODUCT_COLORS = [
        "Red", "Blue", "Green", "Grey", "Pink", "Black", "White"
    ]
    PRODUCT_TYPE = [
        "Shoes", "Socks", "Pants", "Shirt", "Hat", "Gloves", "Vest", "T-Shirt",
        "Sweatshirt", "Skirt", "Dress", "Tie", "Swimsuit"
    ]

    def _get_product():
        color = random.choice(PRODUCT_COLORS)
        category = random.choice(PRODUCT_TYPE)
        now = datetime.datetime.now()

        return {
            "productId": str(uuid.uuid4()),
            "name": "{} {}".format(color, category),
            "createdDate": now.isoformat(),
            "modifiedDate": now.isoformat(),
            "category": category,
            "tags": [color, category],
            "pictures": [
                "https://example.local/{}.jpg".format(random.randrange(0, 1000))
                for _ in range(random.randrange(5, 10))
            ],
            "package": {
                "weight": random.randrange(0, 1000),
                "height": random.randrange(0, 1000),
                "length": random.randrange(0, 1000),
                "width": random.randrange(0, 1000)
            },
            "price": random.randrange(0, 1000)
        }

    return _get_product

@pytest.fixture(scope="module")
def get_inventory(product):

    def _get_inventory(product):

        ship_delay = random.choices(population=[[0,0],[0,1],[1,1],[1,2],[2,2],[2,3],[3,3]],weights=[0.5, 0.2,0.1,0.05,0.05,0.05,0.05],k=7)
        qty = random.randrange(200, 750)
        min_alert = qty//5
        return {
                    "productId" :product["productId"],
                    "name" :product["name"],
                    "category":product["category"],
                    "qty":qty,
                    "min_alert_qty" :min_alert,
                    "ship_delay_reg" :ship_delay[0][1],
                    "ship_delay_prime" :ship_delay[0][0],
                    "registory_ref_no" :"CHALLAN-{}".format(uuid.uuid4()),
                }
    
    return _get_inventory



@pytest.fixture(scope="module")    
def products_db( get_product):

    table =  boto3.resource("dynamodb").Table(product_table) # pylint: disable=no-member

    products = [get_product() for i in range(2)]

    with table.batch_writer() as batch :
        for product in products:
            batch.put_item(Item=product)

    yield products

    with table.batch_writer() as batch :
        for product in products:
            batch.delete_item(Key={"productId" : product["productId"]})



def enrich_inventory(inventory_item):

    now =  datetime.datetime.now()

    id  = str(uuid.uuid4())    

    inventory_item["PK"] =  "INVENTORY#{}".format(inventory_item["productId"])
    inventory_item["SK"] =  "INVENTORY"
    inventory_item["GSK1-PK"] =  "OFF"
    inventory_item["GSK1-SK"] =  now.isoformat()
    inventory_item["updatedDateTime"] =   now.isoformat()

    return inventory_item



@pytest.fixture(scope="module")   
def inventories_db(products_db,get_inventory) :

    inventories = [ get_inventory(p) for p in products_db ]
    
    table =  boto3.resource("dynamodb").Table(warehouse_table) # pylint: disable=no-member

    inventories =  [enrich_inventory(i) for i in inventories]

    with table.batch_writer() as batch :
        for i in inventories:
            batch.put_item(Item=i)

    yield inventories

    with table.batch_writer() as batch :
        for i in inventories:
            batch.delete_item(Key={"PK" :  "INVENTORY#{}".format(i["productId"]),
                            "SK" : "INVENTORY" })


def create_requisition(requistionId,product):

    today =  datetime.date.today()

    return {

        "PK" : "REQUEST#{}".format(requistionId),
        "SK" : "ITEM#{}".format(product["productId"]),
        "GSK1-PK" :"New",
        "GSK1-SK" :str(today),
        "qty":product["qty"],
    }

@pytest.fixture(scope="module")   
def requisition_db(inventories_db):

    reqId  = uuid.uuid4()

    table =  boto3.resource("dynamodb").Table(warehouse_table) # pylint: disable=no-member


    records =[create_requisition(reqId, {"productId" :i["productId"],
                                        "name" :i["name"],
                                        "qty" :REQ_QTY} )
                                         for i in inventories_db ]


    records.append({
                    "PK" :"REQUEST#{}".format(reqId) ,
                    "SK" : "MASTER",
                    "GSK1-PK" :"REQUEST#{}".format("CLIENT_REQ_NO_1"),
                    "GSK1-SK" :"REQUEST#{}".format(reqId),
                    "createdDatetime" :datetime.datetime.now().isoformat(),
                    "status" : "New",
                    "source" :"UNIT_TEST",
                    "reference_no":"ORDER_123"   
                    })
 
    with table.batch_writer() as batch :
        for r in records:
            batch.put_item(Item=r) 
    
    yield records

    with table.batch_writer() as batch :
        for r in records:
            batch.delete_item(Key={"PK" : r["PK"], "SK" :  r["SK"] })


def get_requistion(requistionId):

    table =  boto3.resource("dynamodb").Table(warehouse_table) # pylint: disable=no-member
    response = table.query(
      KeyConditionExpression=Key('PK').eq("REQUEST#{}".format(requistionId)))

    return response["Items"]