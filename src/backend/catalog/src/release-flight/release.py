import json
import os

import boto3
from botocore.exceptions import ClientError
from lumigo_tracer import lumigo_tracer


session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table(os.environ['FLIGHT_TABLE_NAME'])


class FlightReservationException(Exception):
    pass


class FlightFullyBookedException(FlightReservationException):
    pass


class FlightDoesNotExistException(FlightReservationException):
    pass


def reserve_seat_on_flight(flight_id):
    try:
        # TODO: This needs to find the max. In theory, we should never have a situation
        #       where we're trying to increment the seat when one hasn't been
        #       decremented, but just to be sure.
        table.update_item(
            Key={"id": flight_id},
            ConditionExpression="id = :idVal AND seatAllocation < maximumSeating",
            UpdateExpression="SET seatAllocation = seatAllocation + :dec",
            ExpressionAttributeValues={
                ":idVal": flight_id,
                ":dec": 1
            },
        )

        return {
            'status': 'SUCCESS'
        }
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException as e:
        # Due to no specificity from the DDB error, this could also mean the flight
        # doesn't exist, but we should've caught that earlier in the flow.
        # TODO: Fix that. Could either use TransactGetItems, or Get then Update.
        raise FlightFullyBookedException(f"Flight with ID: {flight_id} is fully booked.")
    except ClientError as e:
        raise FlightReservationException(e.response['Error']['Message'])

@lumigo_tracer(token='t_56497e64fb344c4f851e7', edge_host='https://4up6k52vcj.execute-api.us-west-2.amazonaws.com/api/spans', enhance_print=True, should_report=True)
def lambda_handler(event, context):
    if 'outboundFlightId' not in event:
        raise ValueError('Invalid arguments')

    try:
        ret = reserve_seat_on_flight(event['outboundFlightId'])
    except FlightReservationException as e:
        raise FlightReservationException(e)

    return json.dumps(ret)
