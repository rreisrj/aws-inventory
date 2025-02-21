# aws_components/efs.py
from botocore.exceptions import ClientError


class EFSComponent:
    def __init__(self, session):
        self.session = session

    def format_mount_targets(self, mount_targets):
        """Format mount targets information in a readable way"""
        if not mount_targets:
            return {
                "Mount Target IDs": "",
                "Mount Target Subnets": "",
                "Mount Target IPs": "",
                "Mount Target AZs": "",
                "Mount Target Network Interfaces": "",
                "Mount Target Security Groups": "",
            }

        return {
            "Mount Target IDs": "; ".join(mt["MountTargetId"] for mt in mount_targets),
            "Mount Target Subnets": "; ".join(mt["SubnetId"] for mt in mount_targets),
            "Mount Target IPs": "; ".join(mt["IpAddress"] for mt in mount_targets),
            "Mount Target AZs": "; ".join(
                mt.get("AvailabilityZoneName", "") for mt in mount_targets
            ),
            "Mount Target Network Interfaces": "; ".join(
                mt.get("NetworkInterfaceId", "") for mt in mount_targets
            ),
            "Mount Target Security Groups": "; ".join(
                ", ".join(mt.get("SecurityGroups", [])) for mt in mount_targets
            ),
        }

    def format_access_points(self, access_points):
        """Format access points information in a readable way"""
        if not access_points:
            return {
                "Access Point IDs": "",
                "Access Point Names": "",
                "Access Point Root Directories": "",
                "Access Point POSIX Users": "",
                "Access Point Tags": "",
            }

        return {
            "Access Point IDs": "; ".join(ap["AccessPointId"] for ap in access_points),
            "Access Point Names": "; ".join(ap.get("Name", "") for ap in access_points),
            "Access Point Root Directories": "; ".join(
                ap.get("RootDirectory", {}).get("Path", "/") for ap in access_points
            ),
            "Access Point POSIX Users": "; ".join(
                f"UID:{ap.get('PosixUser', {}).get('Uid', 'N/A')},GID:{ap.get('PosixUser', {}).get('Gid', 'N/A')}"
                for ap in access_points
            ),
            "Access Point Tags": "; ".join(
                ",".join(f"{t['Key']}={t['Value']}" for t in ap.get("Tags", []))
                for ap in access_points
            ),
        }

    def format_lifecycle_policies(self, policies):
        """Format lifecycle policies in a readable way"""
        if not policies:
            return "No lifecycle policies"

        formatted = []
        for policy in policies:
            policy_info = [
                f"Transition to IA: {policy.get('TransitionToIA', 'N/A')}",
                f"Transition to Primary: {policy.get('TransitionToPrimaryStorageClass', 'N/A')}",
            ]
            formatted.append(" | ".join(policy_info))

        return "; ".join(formatted)

    def get_resources(self, region):
        """Get EFS file systems information"""
        try:
            efs = self.session.client("efs", region_name=region)
            resources = []

            # Get list of file systems
            paginator = efs.get_paginator("describe_file_systems")
            for page in paginator.paginate():
                for fs in page["FileSystems"]:
                    try:
                        # Extract name from tags
                        name = next(
                            (
                                tag["Value"]
                                for tag in fs.get("Tags", [])
                                if tag["Key"] == "Name"
                            ),
                            fs["FileSystemId"],  # Use FileSystemId if no Name tag
                        )

                        # Get mount targets
                        mount_targets = []
                        try:
                            mt_paginator = efs.get_paginator("describe_mount_targets")
                            for mt_page in mt_paginator.paginate(
                                FileSystemId=fs["FileSystemId"]
                            ):
                                for mt in mt_page["MountTargets"]:
                                    # Get mount target security groups
                                    sg_response = (
                                        efs.describe_mount_target_security_groups(
                                            MountTargetId=mt["MountTargetId"]
                                        )
                                    )
                                    mt["SecurityGroups"] = sg_response.get(
                                        "SecurityGroups", []
                                    )
                                    mount_targets.append(mt)
                        except ClientError as e:
                            print(
                                f"Error getting mount targets for {fs['FileSystemId']}: {str(e)}"
                            )

                        # Get access points
                        access_points = []
                        try:
                            ap_paginator = efs.get_paginator("describe_access_points")
                            for ap_page in ap_paginator.paginate(
                                FileSystemId=fs["FileSystemId"]
                            ):
                                access_points.extend(ap_page["AccessPoints"])
                        except ClientError:
                            pass

                        # Get backup policy
                        backup_policy = "NOT_CONFIGURED"
                        try:
                            backup = efs.describe_backup_policy(
                                FileSystemId=fs["FileSystemId"]
                            )
                            backup_policy = backup["BackupPolicy"]["Status"]
                        except ClientError:
                            pass

                        # Get lifecycle policy
                        lifecycle_policies = []
                        try:
                            lifecycle = efs.describe_lifecycle_configuration(
                                FileSystemId=fs["FileSystemId"]
                            )
                            lifecycle_policies = lifecycle.get("LifecyclePolicies", [])
                        except ClientError:
                            pass

                        # Format mount targets and access points
                        mount_targets_info = self.format_mount_targets(mount_targets)
                        access_points_info = self.format_access_points(access_points)

                        resource_info = {
                            "Region": region,
                            "Service": "EFS",
                            "Resource Name": name,
                            "Resource ID": fs["FileSystemId"],
                            "Creation Time": str(fs.get("CreationTime", "")),
                            "Life Cycle State": fs.get("LifeCycleState", ""),
                            "Size (GB)": round(
                                fs.get("SizeInBytes", {}).get("Value", 0)
                                / (1024 * 1024 * 1024),
                                2,
                            ),
                            "Performance Mode": fs.get("PerformanceMode", ""),
                            "Throughput Mode": fs.get("ThroughputMode", ""),
                            "Provisioned Throughput": fs.get(
                                "ProvisionedThroughputInMibps", "N/A"
                            ),
                            "Encrypted": fs.get("Encrypted", False),
                            "KMS Key ID": fs.get("KmsKeyId", "N/A"),
                            **mount_targets_info,  # Add mount targets columns
                            **access_points_info,  # Add access points columns
                            "Backup Policy": backup_policy,
                            "Lifecycle Policies": self.format_lifecycle_policies(
                                lifecycle_policies
                            ),
                            "File System Policy": str(
                                fs.get("FileSystemPolicy", "N/A")
                            ),
                            "Owner ID": fs.get("OwnerId", ""),
                            "Tags": ",".join(
                                f"{t['Key']}={t['Value']}" for t in fs.get("Tags", [])
                            ),
                            "Available Mount Targets Count": len(mount_targets),
                            "Access Points Count": len(access_points),
                        }

                        resources.append(resource_info)

                    except ClientError as e:
                        print(f"Error processing EFS {fs['FileSystemId']}: {str(e)}")
                        continue

            return resources

        except ClientError as e:
            print(f"Error getting EFS resources in {region}: {str(e)}")
            return []
