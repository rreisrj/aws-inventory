# aws_components/unattached_ebs.py
from botocore.exceptions import ClientError


class UnattachedEBSComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get unattached EBS volumes information"""
        try:
            ec2 = self.session.client("ec2", region_name=region)
            volumes = []

            # Get all volumes
            paginator = ec2.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    # Check if volume has no attachments
                    if not volume.get("Attachments"):
                        name = ""
                        for tag in volume.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                                break

                        volumes.append(
                            {
                                "Region": region,
                                "Service": "UnattachedEBS",
                                "Resource Name": name,
                                "Resource ID": volume["VolumeId"],
                                "Size": f"{volume['Size']} GB",
                                "Volume Type": volume["VolumeType"],
                                "State": volume["State"],
                                "Created": str(volume["CreateTime"]),
                                "Availability Zone": volume["AvailabilityZone"],
                                "Encrypted": str(volume["Encrypted"]),
                                "KMS Key": volume.get("KmsKeyId", "N/A"),
                                "Snapshot ID": volume.get("SnapshotId", "N/A"),
                                "IOPS": volume.get("Iops", "N/A"),
                                "Throughput": volume.get("Throughput", "N/A"),
                                "Multi-Attach Enabled": volume.get(
                                    "MultiAttachEnabled", False
                                ),
                                "Fast Restore Enabled": str(
                                    volume.get("FastRestoreEnabled", False)
                                ),
                                "Tags": str(
                                    [
                                        {t["Key"]: t["Value"]}
                                        for t in volume.get("Tags", [])
                                    ]
                                ),
                            }
                        )

            return volumes
        except ClientError as e:
            print(f"Error getting unattached EBS volumes in {region}: {str(e)}")
            return []
