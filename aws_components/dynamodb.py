# aws_components/dynamodb.py
from botocore.exceptions import ClientError


class DynamoDBComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get DynamoDB tables information"""
        try:
            dynamodb = self.session.client("dynamodb", region_name=region)
            tables = []

            paginator = dynamodb.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page["TableNames"]:
                    try:
                        # Get detailed table information
                        table = dynamodb.describe_table(TableName=table_name)["Table"]

                        # Get table tags
                        try:
                            tags = dynamodb.list_tags_of_resource(
                                ResourceArn=table["TableArn"]
                            )["Tags"]
                        except ClientError:
                            tags = []

                        # Get backup details
                        try:
                            backup_details = dynamodb.describe_continuous_backups(
                                TableName=table_name
                            )["ContinuousBackupsDescription"]
                        except ClientError:
                            backup_details = {}

                        # Get auto scaling settings
                        auto_scaling = {}
                        try:
                            app_auto_scaling = self.session.client(
                                "application-autoscaling", region_name=region
                            )
                            scaling_policies = (
                                app_auto_scaling.describe_scaling_policies(
                                    ServiceNamespace="dynamodb",
                                    ResourceId=f"table/{table_name}",
                                )["ScalingPolicies"]
                            )
                            auto_scaling = {"Policies": scaling_policies}
                        except ClientError:
                            pass

                        # Get TTL status
                        try:
                            ttl = dynamodb.describe_time_to_live(TableName=table_name)[
                                "TimeToLiveDescription"
                            ]
                        except ClientError:
                            ttl = {}

                        tables.append(
                            {
                                "Region": region,
                                "Service": "DynamoDB",
                                "Resource Name": table_name,
                                "Resource ID": table["TableArn"],
                                "Status": table.get("TableStatus", ""),
                                "Creation Date": str(table.get("CreationDateTime", "")),
                                "Item Count": table.get("ItemCount", 0),
                                "Size (Bytes)": table.get("TableSizeBytes", 0),
                                "Provisioned Read Capacity": table.get(
                                    "ProvisionedThroughput", {}
                                ).get("ReadCapacityUnits", 0),
                                "Provisioned Write Capacity": table.get(
                                    "ProvisionedThroughput", {}
                                ).get("WriteCapacityUnits", 0),
                                "Billing Mode": table.get("BillingModeSummary", {}).get(
                                    "BillingMode", "PROVISIONED"
                                ),
                                "Primary Key Schema": str(
                                    [
                                        {
                                            "Name": key["AttributeName"],
                                            "Type": key["KeyType"],
                                        }
                                        for key in table.get("KeySchema", [])
                                    ]
                                ),
                                "Attributes": str(
                                    [
                                        {
                                            "Name": attr["AttributeName"],
                                            "Type": attr["AttributeType"],
                                        }
                                        for attr in table.get(
                                            "AttributeDefinitions", []
                                        )
                                    ]
                                ),
                                "Global Secondary Indexes": str(
                                    [
                                        {
                                            "Name": idx["IndexName"],
                                            "Status": idx["IndexStatus"],
                                            "Size": idx.get("IndexSizeBytes", 0),
                                            "ItemCount": idx.get("ItemCount", 0),
                                        }
                                        for idx in table.get(
                                            "GlobalSecondaryIndexes", []
                                        )
                                    ]
                                ),
                                "Local Secondary Indexes": str(
                                    [
                                        {
                                            "Name": idx["IndexName"],
                                            "Size": idx.get("IndexSizeBytes", 0),
                                            "ItemCount": idx.get("ItemCount", 0),
                                        }
                                        for idx in table.get(
                                            "LocalSecondaryIndexes", []
                                        )
                                    ]
                                ),
                                "Stream Enabled": table.get(
                                    "StreamSpecification", {}
                                ).get("StreamEnabled", False),
                                "Stream Type": table.get("StreamSpecification", {}).get(
                                    "StreamViewType", "N/A"
                                ),
                                "Latest Stream ARN": table.get(
                                    "LatestStreamArn", "N/A"
                                ),
                                "Auto Scaling": str(auto_scaling),
                                "Backup Status": backup_details.get(
                                    "ContinuousBackupsStatus", "N/A"
                                ),
                                "Point In Time Recovery": backup_details.get(
                                    "PointInTimeRecoveryDescription", {}
                                ).get("PointInTimeRecoveryStatus", "N/A"),
                                "TTL Status": ttl.get("TimeToLiveStatus", "N/A"),
                                "TTL Attribute": ttl.get("AttributeName", "N/A"),
                                "Tags": str(tags),
                                "Replicas": str(table.get("Replicas", [])),
                            }
                        )
                    except ClientError as e:
                        print(f"Error getting details for table {table_name}: {str(e)}")
                        continue

            return tables
        except ClientError as e:
            print(f"Error getting DynamoDB resources in {region}: {str(e)}")
            return []
