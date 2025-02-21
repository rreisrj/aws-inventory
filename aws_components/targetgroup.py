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

                    # Format target information
                    target_info = []
                    for target in targets:
                        target_data = {
                            "ID": target.get("Target", {}).get("Id", "N/A"),
                            "IP": target.get("Target", {}).get("Ip", "N/A"),
                            "Port": target.get("Target", {}).get("Port", "N/A"),
                            "Health": target.get("TargetHealth", {}).get(
                                "State", "N/A"
                            ),
                        }
                        target_info.append(target_data)

                    # Format targets for better readability
                    formatted_targets = []
                    for target in target_info:
                        target_str = f"ID: {target['ID']}\n"
                        target_str += f"IP: {target['IP']}\n"
                        target_str += f"Port: {target['Port']}\n"
                        target_str += f"Health: {target['Health']}"
                        formatted_targets.append(target_str)

                    # Format tags for better readability
                    formatted_tags = [f"{k}: {v}" for k, v in tags.items()]

                    target_groups.append(
                        {
                            "Service": "TargetGroup",
                            "Region": region,
                            "Resource Name": tg.get("TargetGroupName", "N/A"),
                            "Resource ID": target_group_arn,
                            "Name": tg.get("TargetGroupName", "N/A"),
                            "ID": target_group_arn,
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
                            "Targets": "\n\n".join(formatted_targets),
                            "Tags": (
                                "\n".join(formatted_tags) if formatted_tags else "N/A"
                            ),
                        }
                    )

        except ClientError as e:
            print(f"Error collecting Target Group information in {region}: {str(e)}")

        return target_groups
