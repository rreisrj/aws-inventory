# aws_components/sqs.py
from botocore.exceptions import ClientError


class SQSComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get SQS queues information"""
        try:
            sqs = self.session.client("sqs", region_name=region)
            queues = []

            # List all queues
            paginator = sqs.get_paginator("list_queues")
            try:
                for page in paginator.paginate():
                    for queue_url in page.get("QueueUrls", []):
                        try:
                            # Get queue attributes
                            attributes = sqs.get_queue_attributes(
                                QueueUrl=queue_url, AttributeNames=["All"]
                            )["Attributes"]

                            # Get queue tags
                            try:
                                tags = sqs.list_queue_tags(QueueUrl=queue_url).get(
                                    "Tags", {}
                                )
                            except ClientError:
                                tags = {}

                            # Get dead-letter queue details if exists
                            dlq_details = {}
                            if "RedrivePolicy" in attributes:
                                import json

                                try:
                                    redrive_policy = json.loads(
                                        attributes["RedrivePolicy"]
                                    )
                                    dlq_details = {
                                        "MaxReceiveCount": redrive_policy.get(
                                            "maxReceiveCount", ""
                                        ),
                                        "DeadLetterTargetArn": redrive_policy.get(
                                            "deadLetterTargetArn", ""
                                        ),
                                    }
                                except (ValueError, KeyError):
                                    pass

                            # Extract queue name from URL
                            queue_name = queue_url.split("/")[-1]

                            queues.append(
                                {
                                    "Region": region,
                                    "Service": "SQS",
                                    "Resource Name": queue_name,
                                    "Resource ID": queue_url,
                                    "Type": (
                                        "FIFO"
                                        if queue_name.endswith(".fifo")
                                        else "Standard"
                                    ),
                                    "ARN": attributes.get("QueueArn", ""),
                                    "Messages Available": attributes.get(
                                        "ApproximateNumberOfMessages", "0"
                                    ),
                                    "Messages in Flight": attributes.get(
                                        "ApproximateNumberOfMessagesNotVisible", "0"
                                    ),
                                    "Messages Delayed": attributes.get(
                                        "ApproximateNumberOfMessagesDelayed", "0"
                                    ),
                                    "Visibility Timeout": attributes.get(
                                        "VisibilityTimeout", ""
                                    ),
                                    "Maximum Message Size": attributes.get(
                                        "MaximumMessageSize", ""
                                    ),
                                    "Message Retention Period": attributes.get(
                                        "MessageRetentionPeriod", ""
                                    ),
                                    "Delay Seconds": attributes.get("DelaySeconds", ""),
                                    "Receive Message Wait Time": attributes.get(
                                        "ReceiveMessageWaitTimeSeconds", ""
                                    ),
                                    "Content-Based Deduplication": attributes.get(
                                        "ContentBasedDeduplication", "false"
                                    ),
                                    "Deduplication Scope": attributes.get(
                                        "DeduplicationScope", "N/A"
                                    ),
                                    "FIFO Throughput Limit": attributes.get(
                                        "FifoThroughputLimit", "N/A"
                                    ),
                                    "KMS Master Key ID": attributes.get(
                                        "KmsMasterKeyId", "N/A"
                                    ),
                                    "KMS Data Key Reuse Period": attributes.get(
                                        "KmsDataKeyReusePeriodSeconds", "N/A"
                                    ),
                                    "Dead Letter Queue": (
                                        str(dlq_details)
                                        if dlq_details
                                        else "Not Configured"
                                    ),
                                    "Policy": attributes.get("Policy", "N/A"),
                                    "Tags": str(tags),
                                    "Created Timestamp": attributes.get(
                                        "CreatedTimestamp", ""
                                    ),
                                    "Last Modified Timestamp": attributes.get(
                                        "LastModifiedTimestamp", ""
                                    ),
                                }
                            )
                        except ClientError as e:
                            print(
                                f"Error getting details for queue {queue_url}: {str(e)}"
                            )
                            continue
            except ClientError as e:
                if "QueueUrls" not in str(e):
                    raise e

            return queues
        except ClientError as e:
            print(f"Error getting SQS resources in {region}: {str(e)}")
            return []
