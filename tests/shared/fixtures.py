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
delivery_table = getParameter("/ecommerce/{}/delivery/table/name".format("test"))
product_table = getParameter("/ecommerce/{}/products/table/name".format("test"))
orders_table_name = getParameter("/ecommerce/{}/orders/table/name".format("test"))
EVENT_BUS_NAME=  getParameter("/ecommerce/{}/platform/event-bus/name".format("test"))

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

def enrich_order(order):

    now =  datetime.datetime.now()

    id  = str(uuid.uuid4())

    order["PK"] =  id
    order["SK"] =  "ORDER#{}".format(id)
    order["orderId"] = id
    order["status"] = "NEW"
    order["createdDate"] = now.isoformat()
    order["modifiedDate"] = now.isoformat()
    order["total"] =  sum([ p["price"]*p.get("quantity",1) for p in order["products"]])
    order["NumOfItems"] = sum([ p.get("quantity",1) for p in order["products"]])

    return order


@pytest.fixture(scope="module")   
def order_db(products_db,get_order):

    # import pdb; pdb.set_trace()
 
    table =  boto3.resource("dynamodb").Table(orders_table_name) # pylint: disable=no-member

    order = get_order(products=products_db)

    order =  enrich_order(order)

    table.put_item(Item=order)

    yield order

    table.delete_item(Key={"PK" :  order["orderId"],
                            "SK" : order["SK"] })


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
                "state": "MA",
                "country": "US",
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
def get_inventory(get_product):

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

    # import pdb; pdb.set_trace()

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

def schedule_record(orderId,productId,sch_date):
    
    return {

            "PK" : "SCHEDULE#{}".format(orderId),
            "SK" : productId,
            "GSK1-PK" : "SCHEDULE#{}".format(sch_date),
            "GSK1-SK" : "New",
            "source" :"UNIT_TEST",
            "createDate": datetime.datetime.now().isoformat(),
            "Note" : "From Pytest fixtures"
        }

@pytest.fixture(scope="module")   
def schedule_db(order_db) :

    table =  boto3.resource("dynamodb").Table(delivery_table) # pylint: disable=no-member

    end_date = datetime.datetime.now() + datetime.timedelta(days=0) 
    sch_date = str(end_date.date())

    records = [schedule_record(order_db["orderId"],p["productId"],sch_date)  
                    for p in order_db["products"]]


    with table.batch_writer() as batch :
        for r in records:
            batch.put_item(Item=r) 
    
    yield records

    with table.batch_writer() as batch :
        for r in records:
            batch.delete_item(Key={"PK" : r["PK"], "SK" :  r["SK"] })

@pytest.fixture(scope="module")   
def package_db(order_db) :

    order = order_db
    token = "UNIT_TEST_123"
    packageId = uuid.uuid4()
    table =  boto3.resource("dynamodb").Table(delivery_table) # pylint: disable=no-member


    master =  {

            "PK" : "PACKAGE#{}".format(packageId),
            "SK" : "MASTER#{}".format(order["orderId"]),
            "status" : "START"  , #START|INPROCESS|COMPLETE|INVOICE|PAYMENT|VALIDATION|READY_FOR_DELIVERY
            "GSK1-PK" : "PACKAGE#START",
            "GSK1-SK" : datetime.datetime.now().isoformat(),
            "createDateTime": datetime.datetime.now().isoformat(),
        }

    item_records = [
        {

            "PK" : "PACKAGE#{}".format(packageId),
            "SK" : "ITEM#{}".format(p["productId"]),
            "createDateTime": datetime.datetime.now().isoformat(),
            "status" : "SCHEDULED"  #SCHEDULED|REQUEST|RELEASE|INPROCESS|PACKED|CANCEL|RESCHEDULE
        } for p in order["products"]
    ]

    token_record =  {

            "PK" : "PACKAGE#{}".format(packageId),
            "SK" : "ORDER_VALIDATE_TOKEN",
            "token" : token ,
            "createDateTime": datetime.datetime.now().isoformat(),
            "status" : "WAIT"  #WAIT|COMPLETE
        }

    shipping_record =  {

            "PK" : "PACKAGE#{}".format(packageId),
            "SK" : "DELIVERY",
            "shipping_address" : order_db["address"],
            "createDateTime": datetime.datetime.now().isoformat(),
        }

    payment_record =  {

            "PK" : "PACKAGE#{}".format(packageId),
            "SK" : "PAYMENT",
            "payment_detail" : order_db["paymentDetail"],
            "createDateTime": datetime.datetime.now().isoformat(),
        }

    records =  [master]+ item_records +  [token_record] + [shipping_record] + [payment_record]

    with table.batch_writer() as batch :
        for r in records:
            batch.put_item(Item=r) 
    
    yield records

    with table.batch_writer() as batch :
        for r in records:
            batch.delete_item(Key={"PK" : r["PK"], "SK" :  r["SK"] })


