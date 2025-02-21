# aws_components/s3.py
from botocore.exceptions import ClientError


class S3Component:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get S3 buckets information including storage class"""
        try:
            s3 = self.session.client("s3")
            s3_control = self.session.client("s3control", region_name=region)
            buckets = []

            # List all buckets
            response = s3.list_buckets()

            for bucket in response["Buckets"]:
                try:
                    # Get bucket location
                    location = s3.get_bucket_location(Bucket=bucket["Name"])
                    bucket_region = location["LocationConstraint"] or "us-east-1"

                    # Only process buckets in current region
                    if bucket_region != region:
                        continue

                    # Get bucket versioning
                    versioning = s3.get_bucket_versioning(Bucket=bucket["Name"])

                    # Get bucket lifecycle rules to determine storage classes
                    storage_classes = set()
                    try:
                        lifecycle = s3.get_bucket_lifecycle_configuration(
                            Bucket=bucket["Name"]
                        )
                        for rule in lifecycle.get("Rules", []):
                            if "Transitions" in rule:
                                for transition in rule["Transitions"]:
                                    if "StorageClass" in transition:
                                        storage_classes.add(transition["StorageClass"])
                    except ClientError:
                        # No lifecycle rules
                        storage_classes.add("STANDARD")  # Default storage class

                    # Get bucket size and object count
                    try:
                        metrics = s3.get_bucket_metrics_configuration(
                            Bucket=bucket["Name"], Id="EntireBucket"
                        )
                        size = metrics.get("BucketSizeBytes", 0)
                        object_count = metrics.get("NumberOfObjects", 0)
                    except ClientError:
                        size = "N/A"
                        object_count = "N/A"

                    # Get encryption status
                    try:
                        encryption = s3.get_bucket_encryption(Bucket=bucket["Name"])
                        encryption_enabled = True
                        encryption_type = encryption[
                            "ServerSideEncryptionConfiguration"
                        ]["Rules"][0]["ApplyServerSideEncryptionByDefault"][
                            "SSEAlgorithm"
                        ]
                    except ClientError:
                        encryption_enabled = False
                        encryption_type = "None"

                    buckets.append(
                        {
                            "Region": region,
                            "Service": "S3",
                            "Resource Name": bucket["Name"],
                            "Resource ID": bucket["Name"],
                            "Creation Date": bucket["CreationDate"].strftime(
                                "%Y-%m-%d"
                            ),
                            "Versioning": versioning.get("Status", "Disabled"),
                            "Storage Classes": str(list(storage_classes)),
                            "Size": size,
                            "Object Count": object_count,
                            "Encryption Enabled": encryption_enabled,
                            "Encryption Type": encryption_type,
                        }
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] == "AccessDenied":
                        print(f"Access denied for bucket {bucket['Name']}")
                    continue

            return buckets
        except ClientError as e:
            print(f"Error getting S3 resources in {region}: {str(e)}")
            return []
