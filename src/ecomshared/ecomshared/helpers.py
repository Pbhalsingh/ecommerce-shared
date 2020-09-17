"""
Helpers for Lambda functions
"""


from datetime import datetime, date
from decimal import Decimal
import json


__all__ = ["Encoder","get_source"]


class Encoder(json.JSONEncoder):
    """
    Helper class to convert a DynamoDB item to JSON
    """

    def default(self, o): # pylint: disable=method-hidden
        if isinstance(o, datetime) or isinstance(o, date):
            return o.isoformat()
        if isinstance(o, Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            return int(o)
        return super(Encoder, self).default(o)

def get_source(event: dict):
    if 'pathParameters' in event and  event['pathParameters'] is not None and 'proxy' in event['pathParameters']:
        return 'api_gateway_aws_proxy'
    elif 'httpMethod' in event and  event['httpMethod'] and event['httpMethod'] in ["GET","POST","PUT","DELETE","PATCH"]:
        return 'api_gateway_aws_proxy'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:s3':
        return 's3'
    elif 'Records' in event and len(event['Records']) > 0 and 'EventSource' in event['Records'][0] and event['Records'][0]['EventSource'] == 'aws:sns':
        return 'sns'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:sns':
        return 'sns'
    elif 'Records' in event and len(event['Records']) > 0 and 'EventSource' in event['Records'][0] and event['Records'][0]['EventSource'] == 'aws:sqs':
        return 'sqs'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:sqs':
        return 'sqs'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:dynamodb':
        return 'dynamo_db'
    elif 'Records' in event and len(event['Records']) > 0 and 'cf' in event['Records'][0]:
        return 'cloudfront'
    elif 'source' in event and event['source'] == 'aws.events':
        return 'scheduled_event'
    elif 'awslogs' in event and 'data' in event['awslogs']:
        return 'cloud_watch_logs'
    elif 'authorizationToken' in event and event['authorizationToken'] == "incoming-client-token":
        return 'api_gateway_authorizer'
    elif 'configRuleId' in event and 'configRuleName' in event and 'configRuleArn' in event:
        return 'aws_config'
    elif 'StackId' in event and 'RequestType' in event and 'ResourceType' in event:
        return 'cloud_formation'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:codecommit':
        return 'code_commit'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:ses':
        return 'ses'
    elif 'Records' in event and len(event['Records']) > 0 and 'eventSource' in event['Records'][0] and event['Records'][0]['eventSource'] == 'aws:kinesis':
        return 'kinesis'
    elif 'records' in event and len(event['Records']) > 0 and 'approximateArrivalTimestamp' in event['records'][0]:
        return 'kinesis_firehose'
    elif 'records' in event and len(event['Records']) > 0 and 'deliveryStreamArn' in event and event['deliveryStreamArn'] is str and event['deliveryStreamArn'].startswith('arn:aws:kinesis:'):
        return 'kinesis_firehose'
    elif 'eventType' in event and event['eventType'] == 'SyncTrigger' and 'identityId' in event and 'identityPoolId' in event:
        return 'cognito_sync_trigger'
    elif 'operation' in event and 'message' in event:
        return 'is_mobile_backend'
    elif 'source' in event and 'detail-type' in event:
        return  'event-bridge'
    elif 'eventType' in event and event['eventType'] == 'request_response':
        return  'request_response'
    else :
        return 'unknown'
