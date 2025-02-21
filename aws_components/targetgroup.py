# aws_components/targetgroup.py
from botocore.exceptions import ClientError


class TargetGroupComponent:
    def __init__(self, session):
        self.session = session

    def get_target_health(self, elbv2_client, target_group_arn):
        """Get health information for targets in a target group"""
        try:
            response = elbv2_client.describe_target_health(
                TargetGroupArn=target_group_arn
            )
            return response.get("TargetHealthDescriptions", [])
        except ClientError as e:
            print(f"Error getting target health for {target_group_arn}: {str(e)}")
            return []

    def get_target_group_tags(self, elbv2_client, target_group_arn):
        """Get tags for a target group"""
        try:
            response = elbv2_client.describe_tags(ResourceArns=[target_group_arn])
            return {
                tag["Key"]: tag["Value"]
                for tag_desc in response.get("TagDescriptions", [])
                for tag in tag_desc.get("Tags", [])
            }
        except ClientError as e:
            print(f"Error getting tags for {target_group_arn}: {str(e)}")
            return {}

    def get_resources(self, region):
        """Get target group information including associated resources"""
        target_groups = []
        try:
            elbv2 = self.session.client("elbv2", region_name=region)
            print(f"Collecting Target Group resources in {region}...")

            paginator = elbv2.get_paginator("describe_target_groups")
            for page in paginator.paginate():
                for tg in page["TargetGroups"]:
                    target_group_arn = tg["TargetGroupArn"]

                    # Get target health information
                    targets = self.get_target_health(elbv2, target_group_arn)

                    # Get tags
                    tags = self.get_target_group_tags(elbv2, target_group_arn)

                    # Format target information into two separate lists
                    target_info = []
                    target_ports = []
                    for target in targets:
                        # Format target ID/IP and health status
                        target_id = target.get("Target", {}).get("Id", "N/A")
                        target_ip = target.get("Target", {}).get("Ip", "N/A")
                        health_state = target.get("TargetHealth", {}).get(
                            "State", "N/A"
                        )

                        target_identifier = (
                            target_id if target_id != "N/A" else target_ip
                        )
                        target_info.append(f"{target_identifier} ({health_state})")

                        # Format port information
                        port = target.get("Target", {}).get("Port", "N/A")
                        protocol = tg.get("Protocol", "N/A")
                        if port != "N/A":
                            target_ports.append(f"{protocol}:{port}")

                    # Format tags for better readability
                    formatted_tags = [f"{k}: {v}" for k, v in tags.items()]

                    target_groups.append(
                        {
                            "Service": "TargetGroup",
                            "Region": region,
                            "Resource Name": tg.get("TargetGroupName", "N/A"),
                            "Resource ID": target_group_arn,
                            "Protocol": tg.get("Protocol", "N/A"),
                            "Port": tg.get("Port", "N/A"),
                            "VpcId": tg.get("VpcId", "N/A"),
                            "HealthCheckProtocol": tg.get("HealthCheckProtocol", "N/A"),
                            "HealthCheckPort": tg.get("HealthCheckPort", "N/A"),
                            "HealthyThresholdCount": tg.get(
                                "HealthyThresholdCount", "N/A"
                            ),
                            "UnhealthyThresholdCount": tg.get(
                                "UnhealthyThresholdCount", "N/A"
                            ),
                            "TargetType": tg.get("TargetType", "N/A"),
                            "LoadBalancerArns": "; ".join(
                                tg.get("LoadBalancerArns", [])
                            ),
                            "Targets": "\n".join(target_info) if target_info else "N/A",
                            "Target Ports": (
                                "\n".join(target_ports) if target_ports else "N/A"
                            ),
                            "Tags": (
                                "\n".join(formatted_tags) if formatted_tags else "N/A"
                            ),
                        }
                    )

            print(f"  Found {len(target_groups)} Target Group resources in {region}")
            return target_groups
        except ClientError as e:
            print(f"Error getting Target Group resources in {region}: {str(e)}")
            return []
