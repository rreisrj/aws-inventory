# aws_components/sns.py
import json

from botocore.exceptions import ClientError


class SNSComponent:
    def __init__(self, session):
        self.session = session

    def format_policy(self, policy):
        """Format SNS policy in proper JSON format"""
        if not policy:
            return "{}"

        try:
            # If policy is already a dict, convert to formatted JSON string
            if isinstance(policy, dict):
                return json.dumps(policy, indent=2)
            # If policy is a string, parse it and format
            return json.dumps(json.loads(policy), indent=2)
        except (json.JSONDecodeError, TypeError):
            return str(policy)

    def get_resources(self, region):
        """Get SNS topics information"""
        try:
            sns = self.session.client("sns", region_name=region)
            topics = []

            # List all topics
            paginator = sns.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page["Topics"]:
                    try:
                        topic_arn = topic["TopicArn"]
                        topic_name = topic_arn.split(":")[-1]

                        # Get topic attributes
                        attributes = sns.get_topic_attributes(TopicArn=topic_arn)[
                            "Attributes"
                        ]

                        # Get topic tags
                        try:
                            tags = sns.list_tags_for_resource(ResourceArn=topic_arn)[
                                "Tags"
                            ]
                        except ClientError:
                            tags = []

                        # Get subscriptions for this topic
                        subscriptions = []
                        try:
                            sub_paginator = sns.get_paginator(
                                "list_subscriptions_by_topic"
                            )
                            for sub_page in sub_paginator.paginate(TopicArn=topic_arn):
                                for sub in sub_page["Subscriptions"]:
                                    # Get subscription attributes
                                    sub_attributes = {}
                                    if "PendingConfirmation" not in sub.get(
                                        "SubscriptionArn", ""
                                    ):
                                        try:
                                            sub_attributes = (
                                                sns.get_subscription_attributes(
                                                    SubscriptionArn=sub[
                                                        "SubscriptionArn"
                                                    ]
                                                )["Attributes"]
                                            )
                                        except ClientError:
                                            pass

                                    subscriptions.append(
                                        {
                                            "Protocol": sub.get("Protocol", ""),
                                            "Endpoint": sub.get("Endpoint", ""),
                                            "SubscriptionArn": sub.get(
                                                "SubscriptionArn", ""
                                            ),
                                            "Status": (
                                                "Confirmed"
                                                if "PendingConfirmation"
                                                not in sub.get("SubscriptionArn", "")
                                                else "Pending"
                                            ),
                                            "RawMessageDelivery": sub_attributes.get(
                                                "RawMessageDelivery", "false"
                                            ),
                                            "FilterPolicy": sub_attributes.get(
                                                "FilterPolicy", "None"
                                            ),
                                            "RedrivePolicy": sub_attributes.get(
                                                "RedrivePolicy", "None"
                                            ),
                                            "DeliveryPolicy": sub_attributes.get(
                                                "DeliveryPolicy", "None"
                                            ),
                                        }
                                    )
                        except ClientError:
                            pass

                        # Get FIFO details if applicable
                        fifo_details = {}
                        if topic_name.endswith(".fifo"):
                            fifo_details = {
                                "ContentBasedDeduplication": attributes.get(
                                    "ContentBasedDeduplication", "false"
                                ),
                                "FifoTopic": "true",
                                "DeduplicationScope": attributes.get(
                                    "DeduplicationScope", "N/A"
                                ),
                                "FifoThroughputLimit": attributes.get(
                                    "FifoThroughputLimit", "N/A"
                                ),
                            }

                        # Format delivery policy if exists
                        delivery_policy = attributes.get("DeliveryPolicy", "N/A")
                        if delivery_policy != "N/A":
                            try:
                                delivery_policy = json.loads(delivery_policy)
                            except (ValueError, TypeError):
                                pass

                        # Format policy
                        policy = self.format_policy(attributes.get("Policy"))

                        topics.append(
                            {
                                "Region": region,
                                "Service": "SNS",
                                "Resource Name": topic_name,
                                "Resource ID": topic_arn,
                                "Display Name": attributes.get("DisplayName", ""),
                                "Type": (
                                    "FIFO"
                                    if topic_name.endswith(".fifo")
                                    else "Standard"
                                ),
                                "Subscriptions Count": len(subscriptions),
                                "Subscriptions": str(subscriptions),
                                "FIFO Details": (
                                    str(fifo_details) if fifo_details else "N/A"
                                ),
                                "Effective Delivery Policy": str(delivery_policy),
                                "Policy": policy,
                                "KMS Master Key ID": attributes.get(
                                    "KmsMasterKeyId", "N/A"
                                ),
                                "Owner": attributes.get("Owner", ""),
                                "Subscriptions Pending": attributes.get(
                                    "SubscriptionsPending", "0"
                                ),
                                "Subscriptions Confirmed": attributes.get(
                                    "SubscriptionsConfirmed", "0"
                                ),
                                "Subscriptions Deleted": attributes.get(
                                    "SubscriptionsDeleted", "0"
                                ),
                                "HTTP Success Feedback Role": attributes.get(
                                    "HTTPSuccessFeedbackRoleArn", "N/A"
                                ),
                                "HTTP Failure Feedback Role": attributes.get(
                                    "HTTPFailureFeedbackRoleArn", "N/A"
                                ),
                                "Lambda Success Feedback Role": attributes.get(
                                    "LambdaSuccessFeedbackRoleArn", "N/A"
                                ),
                                "Lambda Failure Feedback Role": attributes.get(
                                    "LambdaFailureFeedbackRoleArn", "N/A"
                                ),
                                "SQS Success Feedback Role": attributes.get(
                                    "SQSSuccessFeedbackRoleArn", "N/A"
                                ),
                                "SQS Failure Feedback Role": attributes.get(
                                    "SQSFailureFeedbackRoleArn", "N/A"
                                ),
                                "HTTP Success Feedback Sample Rate": attributes.get(
                                    "HTTPSuccessFeedbackSampleRate", "N/A"
                                ),
                                "Lambda Success Feedback Sample Rate": attributes.get(
                                    "LambdaSuccessFeedbackSampleRate", "N/A"
                                ),
                                "SQS Success Feedback Sample Rate": attributes.get(
                                    "SQSSuccessFeedbackSampleRate", "N/A"
                                ),
                                "Application Success Feedback Role": attributes.get(
                                    "ApplicationSuccessFeedbackRoleArn", "N/A"
                                ),
                                "Application Failure Feedback Role": attributes.get(
                                    "ApplicationFailureFeedbackRoleArn", "N/A"
                                ),
                                "Application Success Feedback Sample Rate": attributes.get(
                                    "ApplicationSuccessFeedbackSampleRate", "N/A"
                                ),
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
                        print(f"Error getting details for topic {topic_arn}: {str(e)}")
                        continue

            return topics
        except ClientError as e:
            print(f"Error getting SNS resources in {region}: {str(e)}")
            return []
