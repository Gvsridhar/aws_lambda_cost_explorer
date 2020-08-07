import boto3
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
            'Value': 0.0000056000
        },
    ],
    Namespace='Lambda'
)
print(f"{response}")