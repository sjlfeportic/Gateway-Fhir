import os
import re
import time
from base64 import b64encode, b64decode
from hashlib import sha256
from hmac import HMAC
import asyncio
from urllib.parse import urlencode, quote_plus
from uamqp import ReceiveClient, Source
from uamqp.errors import LinkRedirect
import http.client
import json

from azure.eventhub.aio import EventHubConsumerClient


def generate_sas_token(uri, policy, key, expiry=None):
    """Create a shared access signiture token as a string literal.
    :returns: SAS token as string literal.
    :rtype: str
    """
    if not expiry:
        expiry = time.time() + 3600
    encoded_uri = quote_plus(uri)
    ttl = int(expiry)
    sign_key = '%s\n%d' % (encoded_uri, ttl)
    signature = b64encode(HMAC(b64decode(key), sign_key.encode('utf-8'), sha256).digest())
    result = {
        'sr': uri,
        'sig': signature,
        'se': str(ttl)}
    if policy:
        result['skn'] = policy
    return 'SharedAccessSignature ' + urlencode(result)


def parse_iot_conn_str(iothub_conn_str):
    hostname = None
    shared_access_key_name = None
    shared_access_key = None
    for element in iothub_conn_str.split(';'):
        key, _, value = element.partition('=')
        if key.lower() == 'hostname':
            hostname = value.rstrip('/')
        elif key.lower() == 'sharedaccesskeyname':
            shared_access_key_name = value
        elif key.lower() == 'sharedaccesskey':
            shared_access_key = value
    if not all([hostname, shared_access_key_name, shared_access_key]):
        raise ValueError("Invalid connection string")
    return hostname, shared_access_key_name, shared_access_key


def convert_iothub_to_eventhub_conn_str(iothub_conn_str):
    hostname, shared_access_key_name, shared_access_key = parse_iot_conn_str(iothub_conn_str)
    iot_hub_name = hostname.split(".")[0]
    operation = '/messages/events/ConsumerGroups/{}/Partitions/{}'.format('$Default', 0)
    username = '{}@sas.root.{}'.format(shared_access_key_name, iot_hub_name)
    sas_token = generate_sas_token(hostname, shared_access_key_name, shared_access_key)
    uri = 'amqps://{}:{}@{}{}'.format(quote_plus(username),
                                      quote_plus(sas_token), hostname, operation)
    source_uri = Source(uri)
    receive_client = ReceiveClient(source_uri)
    try:
        receive_client.receive_message_batch(max_batch_size=1)
    except LinkRedirect as redirect:
        # Once a redirect error is received, close the original client and recreate a new one to the re-directed address
        receive_client.close()
        fully_qualified_name = redirect.hostname.decode("utf-8")
        # Use regular expression to parse the Event Hub name from the IoT Hub redirection address
        if redirect.address:
            # The regex searches for the Event Hub compatible name in the redirection address. The name is nested in
            # between the port and 'ConsumerGroups'.
            # (ex. "...servicebus.windows.net:12345/<Event Hub name>/ConsumerGroups/...").
            # The regex matches string ':<digits>/', then any characters, then the string '/ConsumerGroups'.
            iot_hub_name = re.search(":\d+\/.*/ConsumerGroups", str(redirect.address)).group(0).split("/")[1]
        return "Endpoint=sb://{}/;SharedAccessKeyName={};SharedAccessKey={};EntityPath={}".format(
            fully_qualified_name,
            shared_access_key_name,
            shared_access_key,
            iot_hub_name
        )
    except Exception as exp:
        raise ValueError(
            "{} is not an invalid IoT Hub connection string. The underlying exception is {}".format(
                iothub_conn_str,
                exp,
            )
        )


async def receive_events_from_iothub(iothub_conn_str):
    """Convert the iot hub connection string to the built-in eventhub connection string
    and receive events from the eventhub
    """
    eventhub_conn_str = convert_iothub_to_eventhub_conn_str(iothub_conn_str)
    consumer_client = EventHubConsumerClient.from_connection_string(eventhub_conn_str, consumer_group="$Default")

    async def on_event_batch(partition_context, event_batch):
        # put your code here
        #print("received {} events from partition {}".format((event_batch), partition_context.partition_id))
        #print(event_batch)
        string=str(event_batch)
        stringspo2=string[24:28]
        #numerodospo2=float(stringspo2)
        #print(numerodospo2)
        stringbatimentos=string[53:57]
        #numerodebatimentos=float(stringbatimentos)
        #print(numerodebatimentos)
        #print(string[24:28])
        #m=(re.search(r'\d+', str(event_batch)))
        #print(m.group())
        ok="estevao"
        conn = http.client.HTTPSConnection("dumpdados.azurehealthcareapis.com")
        payload = json.dumps({
            "resourceType": "Patient",
            "active": True,
            "name": [
                {
                "use": "official",
                "family": "Teixeira",
                "given": [
                    "Rui",
                    "Manuel"
                ]
                },
                {
                "use": "usual",
                "given": [
                    stringspo2
                ]
                }
            ],
            "gender": "male",
            "birthDate": "1980-12-25"
            })
        headers = {
            'Authorization': 'Bearer token',
            'Content-Type': 'application/json'
        }
        conn.request("POST", "/Patient", payload, headers)
        res = conn.getresponse()
        data = res.read()
        print(data.decode("utf-8"))    

    async with consumer_client:
        await consumer_client.receive_batch(
            on_event_batch,
            starting_position=-1  # "-1" is from the beginning of the partition.
        )


if __name__ == '__main__':
    asyncio.run(receive_events_from_iothub('azure_code'))