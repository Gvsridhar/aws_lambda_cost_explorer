import boto3
from decimal import Decimal, getcontext

def calculate_cost():

    client = boto3.client('ce')
    result = client.get_cost_and_usage(
        TimePeriod = {
            'Start': '2020-08-06',
            'End': '2020-08-07'
        },
        Granularity = 'DAILY',
        Filter = 
                {
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": ['AWS Lambda']
                    }
                },
        Metrics = ["BlendedCost"],
        GroupBy = [
            {
                'Type': 'TAG',
                'Key': 'app'
            }
        ]
    )
    resultsByTime = result.get('ResultsByTime')
    for item in resultsByTime:
        if item.get('Groups'):
            #print(item)
            oneDayCost = item.get('Groups')[0].get('Metrics').get('BlendedCost').get('Amount')
            #print(f"{oneDayCost}")
            return oneDayCost

def push_cost_metric_to_cloudwatch(oneDayCost):
    """
    Sends custom cost metric to cloudwatch AWS/Lambda namespace.
    :param lambdas_data: List of Lambda functions data.
    :return: None.
    """
    cloudwatch = boto3.client('cloudwatch', 'us-west-2')

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
                'Value': oneDayCost
            },
        ],
        Namespace='Lambda'
    )
    print(f"{response}")

if __name__ == '__main__':
   oneDayCost = calculate_cost()
   getcontext().prec = 20
   #oneDayCost = Decimal(oneDayCost)
   oneDayCost = '{0:1f}'.format(Decimal(oneDayCost))
   print(f"{float(oneDayCost)}")
   #push_cost_metric_to_cloudwatch(oneDayCost)
  

