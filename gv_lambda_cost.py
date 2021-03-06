"""
Forecasts Lambda functions costs based on last day.
"""

from __future__ import print_function
from datetime import datetime, timedelta
import argparse
import codecs
import boto3
from math import ceil
from boto3.session import Session
from terminaltables import AsciiTable
import progressbar
from consts import (
    TABLE_HEADERS,
    CONSOLE_TABLE_HEADERS,
    PRICE_INTERVALS_MS,
    PRICE_PER_INVOCATION,
    get_price_by_memory
)

RESULT_NA = 'N/A'

def lambda_handler(event, context):
    """
    Main function.
    :param args: script arguments.
    :return: None.
    """
    lambdas_data = []
    total_monthly_cost = 0
    lambda_client = boto3.client('lambda')
    cloudwatch_client = boto3.client('cloudwatch')
    next_marker = None
    response = lambda_client.list_functions()
    while next_marker != '':
        next_marker = ''
        functions = response['Functions']
        if not functions:
            continue
        print(f"{functions}")

        for function_data in functions:
            if 'Lambda' in function_data['FunctionName']:
                sum_invocations = get_cloudwatch_metric(
                    cloudwatch_client,
                    'Invocations',
                    'Sum',
                    function_data['FunctionName']
                )

                avg_duration = get_cloudwatch_metric(
                    cloudwatch_client,
                    'Duration',
                    'Average',
                    function_data['FunctionName']
                )

                period_cost = calculate_cost(
                    avg_duration,
                    sum_invocations,
                    function_data['MemorySize']
                )
                print(f"period cost is {period_cost}")

                lambdas_data.append((
                    function_data['FunctionName'],
                    function_data['MemorySize'],
                    RESULT_NA if avg_duration == 0 else int(avg_duration),
                    RESULT_NA if avg_duration == 0 else int(sum_invocations),
                    RESULT_NA if avg_duration == 0 else '{0:.10f}'.format(
                        period_cost
                    ),
                    RESULT_NA if avg_duration == 0 else '{0:.10f}'.format(
                        period_cost * 30,
                    ),
                ))
                total_monthly_cost += (period_cost * 30)

        # Verify if there is next marker.
        if 'NextMarker' in response:
            next_marker = response['NextMarker']
            response = lambda_client.list_functions(Marker=next_marker)

    # Sort data by the cost.
    lambdas_data.sort(
        key=lambda x: 0 if x[4] == RESULT_NA else float(x[4]),
        reverse=True
    )
    
    #print_table_to_console(lambdas_data)
    #print('Total monthly cost estimation: ${0:.3f}'.format(total_monthly_cost))
    push_cost_metric_to_cloudwatch(lambdas_data)
    #if not args.csv:
    #    return

    #lambdas_data.insert(0, TABLE_HEADERS)
    #with codecs.open(args.csv, 'w', encoding='utf-8') as output_file:
    #    for table_row in lambdas_data:
    #        output_file.writelines(
    #            '{0}\n'.format(','.join([str(x) for x in table_row]))
    #        )


def list_available_lambda_regions():
    """
    Enumerates list of all Lambda regions.
    :return: list of regions
    """
    session = Session()
    return session.get_available_regions('lambda')


def init_boto_client(client_name, region, args):
    """
    Initiates boto's client object.
    :param client_name: client name.
    :param region: region name.
    :param args: arguments.
    :return: Client.
    """
    if args.token_key_id and args.token_secret:
        boto_client = boto3.client(
            client_name,
            aws_access_key_id=args.token_key_id,
            aws_secret_access_key=args.token_secret,
            region_name=region
        )
    elif args.profile:
        session = Session(profile_name=args.profile, region_name=region)
        boto_client = session.client(client_name, region_name=region)
    else:
        boto_client = boto3.client(client_name, region_name=region)

    return boto_client


def get_cloudwatch_metric(
        cloudwatch_client,
        metric_name,
        statistic,
        function_name
    ):
    """
    Returns a CloudWatch Metric statistic.
    :param cloudwatch_client: Client.
    :param metric_name: Metric name.
    :param statistic: Statistic type
    :param function_name: Function name.
    :return: Statistic value or 0 if not exists.
    """
    result = cloudwatch_client.get_metric_statistics(
        Period=int(timedelta(days=1).total_seconds()),
        StartTime=datetime.utcnow() - timedelta(days=1),
        EndTime=datetime.utcnow(),
        MetricName=metric_name,
        Namespace='AWS/Lambda',
        Statistics=[statistic],
        Dimensions=[{
            'Name':'FunctionName',
            'Value': function_name
        }]
    )

    return result['Datapoints'][0][statistic] if (result['Datapoints']) else 0


def calculate_cost(avg_duration, sum_invocations, memory_size):
    """
    Calculate cost based on AWS Lambda pricing.
    :param avg_duration: Avg. duration of function.
    :param sum_invocations: Count of invocations of function.
    :param memory_size: Function's memory size.
    :return: cost.
    """
    #price = get_price_by_memory(memory_size)
    #print(f"{avg_duration}, {sum_invocations}, {memory_size}, {price}")
    print(f"{ceil(avg_duration / PRICE_INTERVALS_MS)*(get_price_by_memory(memory_size))}")
    print(f"Sum is {(sum_invocations * PRICE_PER_INVOCATION)}")
    value1 = ceil(avg_duration / PRICE_INTERVALS_MS)*(get_price_by_memory(memory_size))
    value2 = sum_invocations * PRICE_PER_INVOCATION
    value3 = value1 + value2
    print(f"Total value is {value3}")
    return value3

def push_cost_metric_to_cloudwatch(lambdas_data):
    """
    Sends custom cost metric to cloudwatch AWS/Lambda namespace.
    :param lambdas_data: List of Lambda functions data.
    :return: None.
    """
    cloudwatch = boto3.client('cloudwatch')

    response = cloudwatch.put_metric_data(
        MetricData = [
            {
                'MetricName': 'LastOneDayCost',
                'Dimensions': [
                    {
                        'Name': 'By Function Name',
                        'Value': 'LambdaLogging'
                    }
                ],
                'Unit': 'None',
                'Value': lambdas_data[5]
            },
        ],
        Namespace='Lambda'
    )
    print(f"{response}")

def print_table_to_console(lambdas_data):
    """
    Prints the minified version to console.
    :param lambdas_data: List of Lambda functions data.
    :return: None.
    """
    lambdas_data = [(x[0], x[1], x[4], x[5]) for x in lambdas_data]
    lambdas_data.insert(0, CONSOLE_TABLE_HEADERS)
    table = AsciiTable(lambdas_data)
    print(table.table)

