# aws_components/autoscaling.py
from datetime import datetime

from botocore.exceptions import ClientError


class AutoScalingComponent:
    def __init__(self, session):
        self.session = session

    # [Previous formatting methods remain the same until get_resources]

    def format_launch_config(self, config):
        """Format launch configuration or template in a readable way"""
        if not config:
            return "No launch configuration"

        formatted = []
        formatted.extend(
            [
                f"Type: {config.get('Type', 'N/A')}",
                f"Name: {config.get('Name', 'N/A')}",
                f"Image ID: {config.get('ImageId', 'N/A')}",
                f"Instance Type: {config.get('InstanceType', 'N/A')}",
                f"Security Groups: {', '.join(config.get('SecurityGroups', []))}",
            ]
        )

        return " | ".join(formatted)

    def format_instances(self, instances):
        """Format instances information in a readable way"""
        if not instances:
            return {
                "Instance IDs": "",
                "Instance States": "",
                "Instance Types": "",
                "Private IPs": "",
                "Public IPs": "",
            }

        formatted = {
            "Instance IDs": [],
            "Instance States": [],
            "Instance Types": [],
            "Private IPs": [],
            "Public IPs": [],
        }

        for instance in instances:
            formatted["Instance IDs"].append(instance["InstanceId"])
            formatted["Instance States"].append(
                f"{instance['LifecycleState']}({instance['HealthStatus']})"
            )
            formatted["Instance Types"].append(instance.get("InstanceType", "N/A"))
            formatted["Private IPs"].append(instance.get("PrivateIP", "N/A"))
            formatted["Public IPs"].append(instance.get("PublicIP", "N/A"))

        return {
            "Instance IDs": "; ".join(formatted["Instance IDs"]),
            "Instance States": "; ".join(formatted["Instance States"]),
            "Instance Types": "; ".join(formatted["Instance Types"]),
            "Private IPs": "; ".join(formatted["Private IPs"]),
            "Public IPs": "; ".join(formatted["Public IPs"]),
        }

    def format_scaling_policies(self, policies):
        """Format scaling policies in a readable way"""
        if not policies:
            return {
                "Policy Names": "",
                "Policy Types": "",
                "Adjustments": "",
                "Cooldowns": "",
            }

        formatted = {
            "Policy Names": [],
            "Policy Types": [],
            "Adjustments": [],
            "Cooldowns": [],
        }

        for policy in policies:
            formatted["Policy Names"].append(policy.get("PolicyName", "N/A"))
            formatted["Policy Types"].append(policy.get("PolicyType", "N/A"))

            # Format adjustment
            adjustment = ""
            if "ScalingAdjustment" in policy:
                adjustment = f"{policy['ScalingAdjustment']} instances"
            elif "TargetTrackingConfiguration" in policy:
                target = policy["TargetTrackingConfiguration"]
                adjustment = f"Target {target.get('TargetValue', 'N/A')} {target.get('PredefinedMetricSpecification', {}).get('PredefinedMetricType', 'N/A')}"
            formatted["Adjustments"].append(adjustment or "N/A")

            formatted["Cooldowns"].append(str(policy.get("Cooldown", "N/A")))

        return {
            "Policy Names": "; ".join(formatted["Policy Names"]),
            "Policy Types": "; ".join(formatted["Policy Types"]),
            "Policy Adjustments": "; ".join(formatted["Adjustments"]),
            "Policy Cooldowns": "; ".join(formatted["Cooldowns"]),
        }

    def format_scheduled_actions(self, actions):
        """Format scheduled actions in a readable way"""
        if not actions:
            return {
                "Action Names": "",
                "Start Times": "",
                "End Times": "",
                "Recurrences": "",
                "Desired Capacities": "",
            }

        formatted = {
            "Action Names": [],
            "Start Times": [],
            "End Times": [],
            "Recurrences": [],
            "Desired Capacities": [],
        }

        for action in actions:
            formatted["Action Names"].append(action.get("ScheduledActionName", "N/A"))
            formatted["Start Times"].append(str(action.get("StartTime", "N/A")))
            formatted["End Times"].append(str(action.get("EndTime", "N/A")))
            formatted["Recurrences"].append(action.get("Recurrence", "N/A"))
            formatted["Desired Capacities"].append(
                str(action.get("DesiredCapacity", "N/A"))
            )

        return {
            "Action Names": "; ".join(formatted["Action Names"]),
            "Action Start Times": "; ".join(formatted["Start Times"]),
            "Action End Times": "; ".join(formatted["End Times"]),
            "Action Recurrences": "; ".join(formatted["Recurrences"]),
            "Action Desired Capacities": "; ".join(formatted["Desired Capacities"]),
        }

    def get_launch_template_data(self, ec2, template_id, version):
        """Get launch template data for a specific version"""
        try:
            response = ec2.describe_launch_template_versions(
                LaunchTemplateId=template_id, Versions=[str(version)]
            )
            if response["LaunchTemplateVersions"]:
                return response["LaunchTemplateVersions"][0]["LaunchTemplateData"]
        except ClientError as e:
            print(f"Error getting launch template data for {template_id}: {str(e)}")
        return {}

    def get_resources(self, region):
        """Get Auto Scaling groups information"""
        try:
            asg = self.session.client("autoscaling", region_name=region)
            ec2 = self.session.client("ec2", region_name=region)
            groups = []

            # Get Auto Scaling groups
            paginator = asg.get_paginator("describe_auto_scaling_groups")
            for page in paginator.paginate():
                for group in page["AutoScalingGroups"]:
                    try:
                        # Get instances information
                        instance_ids = [i["InstanceId"] for i in group["Instances"]]
                        instance_details = {}

                        # Batch describe instances in chunks of 100
                        for i in range(0, len(instance_ids), 100):
                            chunk = instance_ids[i : i + 100]
                            try:
                                response = ec2.describe_instances(InstanceIds=chunk)
                                for reservation in response["Reservations"]:
                                    for instance in reservation["Instances"]:
                                        instance_details[instance["InstanceId"]] = (
                                            instance
                                        )
                            except ClientError as e:
                                print(f"Error describing instances {chunk}: {str(e)}")

                        instances = []
                        for instance in group["Instances"]:
                            instance_info = {
                                "InstanceId": instance["InstanceId"],
                                "LifecycleState": instance["LifecycleState"],
                                "HealthStatus": instance["HealthStatus"],
                                "LaunchConfigurationName": instance.get(
                                    "LaunchConfigurationName", ""
                                ),
                                "LaunchTemplate": instance.get("LaunchTemplate", {}),
                            }

                            # Add EC2 instance details if available
                            if instance["InstanceId"] in instance_details:
                                ec2_instance = instance_details[instance["InstanceId"]]
                                instance_info.update(
                                    {
                                        "Name": next(
                                            (
                                                tag["Value"]
                                                for tag in ec2_instance.get("Tags", [])
                                                if tag["Key"] == "Name"
                                            ),
                                            "No Name",
                                        ),
                                        "InstanceType": ec2_instance["InstanceType"],
                                        "PrivateIP": ec2_instance.get(
                                            "PrivateIpAddress", "N/A"
                                        ),
                                        "PublicIP": ec2_instance.get(
                                            "PublicIpAddress", "N/A"
                                        ),
                                    }
                                )

                            instances.append(instance_info)

                        # Get launch configuration or template
                        launch_config = {}
                        if group.get("LaunchConfigurationName"):
                            try:
                                launch_config_response = (
                                    asg.describe_launch_configurations(
                                        LaunchConfigurationNames=[
                                            group["LaunchConfigurationName"]
                                        ]
                                    )
                                )
                                if launch_config_response["LaunchConfigurations"]:
                                    lc = launch_config_response["LaunchConfigurations"][
                                        0
                                    ]
                                    launch_config = {
                                        "Type": "LaunchConfiguration",
                                        "Name": lc["LaunchConfigurationName"],
                                        "ImageId": lc["ImageId"],
                                        "InstanceType": lc["InstanceType"],
                                        "SecurityGroups": lc.get("SecurityGroups", []),
                                    }
                            except ClientError as e:
                                print(f"Error getting launch configuration: {str(e)}")

                        elif group.get("LaunchTemplate"):
                            try:
                                lt = group["LaunchTemplate"]
                                launch_template = ec2.describe_launch_templates(
                                    LaunchTemplateIds=[lt["LaunchTemplateId"]]
                                )["LaunchTemplates"][0]

                                # Get the specific version's data
                                version = lt.get("Version", "$Latest")
                                template_data = self.get_launch_template_data(
                                    ec2, lt["LaunchTemplateId"], version
                                )

                                launch_config = {
                                    "Type": "LaunchTemplate",
                                    "Name": launch_template["LaunchTemplateName"],
                                    "ImageId": template_data.get("ImageId", "N/A"),
                                    "InstanceType": template_data.get(
                                        "InstanceType", "N/A"
                                    ),
                                    "SecurityGroups": (
                                        [
                                            sg["GroupId"]
                                            for sg in template_data.get(
                                                "SecurityGroups", []
                                            )
                                        ]
                                        if isinstance(
                                            template_data.get("SecurityGroups", []),
                                            list,
                                        )
                                        else template_data.get("SecurityGroups", [])
                                    ),
                                }
                            except ClientError as e:
                                print(f"Error getting launch template: {str(e)}")

                        elif group.get("MixedInstancesPolicy"):
                            try:
                                mixed_policy = group["MixedInstancesPolicy"]
                                lt = mixed_policy["LaunchTemplate"][
                                    "LaunchTemplateSpecification"
                                ]
                                launch_template = ec2.describe_launch_templates(
                                    LaunchTemplateIds=[lt["LaunchTemplateId"]]
                                )["LaunchTemplates"][0]

                                # Get the specific version's data
                                version = lt.get("Version", "$Latest")
                                template_data = self.get_launch_template_data(
                                    ec2, lt["LaunchTemplateId"], version
                                )

                                # Get instance types from the policy
                                instance_types = []
                                if "Overrides" in mixed_policy["LaunchTemplate"]:
                                    instance_types = [
                                        override.get("InstanceType", "N/A")
                                        for override in mixed_policy["LaunchTemplate"][
                                            "Overrides"
                                        ]
                                    ]

                                launch_config = {
                                    "Type": "MixedInstancesPolicy",
                                    "Name": launch_template["LaunchTemplateName"],
                                    "ImageId": template_data.get("ImageId", "N/A"),
                                    "InstanceType": (
                                        ", ".join(instance_types)
                                        if instance_types
                                        else template_data.get("InstanceType", "N/A")
                                    ),
                                    "SecurityGroups": (
                                        [
                                            sg["GroupId"]
                                            for sg in template_data.get(
                                                "SecurityGroups", []
                                            )
                                        ]
                                        if isinstance(
                                            template_data.get("SecurityGroups", []),
                                            list,
                                        )
                                        else template_data.get("SecurityGroups", [])
                                    ),
                                }
                            except ClientError as e:
                                print(f"Error getting mixed instances policy: {str(e)}")

                        # Get scaling policies
                        policies = []
                        try:
                            policies_response = asg.describe_policies(
                                AutoScalingGroupName=group["AutoScalingGroupName"]
                            )
                            policies = policies_response["ScalingPolicies"]
                        except ClientError as e:
                            print(f"Error getting scaling policies: {str(e)}")

                        # Get scheduled actions
                        scheduled_actions = []
                        try:
                            actions_response = asg.describe_scheduled_actions(
                                AutoScalingGroupName=group["AutoScalingGroupName"]
                            )
                            scheduled_actions = actions_response[
                                "ScheduledUpdateGroupActions"
                            ]
                        except ClientError as e:
                            print(f"Error getting scheduled actions: {str(e)}")

                        # Get notifications
                        notifications = []
                        try:
                            notif_response = asg.describe_notification_configurations(
                                AutoScalingGroupNames=[group["AutoScalingGroupName"]]
                            )
                            notifications = notif_response["NotificationConfigurations"]
                        except ClientError as e:
                            print(f"Error getting notifications: {str(e)}")

                        # Get lifecycle hooks
                        lifecycle_hooks = []
                        try:
                            hooks_response = asg.describe_lifecycle_hooks(
                                AutoScalingGroupName=group["AutoScalingGroupName"]
                            )
                            lifecycle_hooks = hooks_response["LifecycleHooks"]
                        except ClientError as e:
                            print(f"Error getting lifecycle hooks: {str(e)}")

                        # Update the resource dictionary to use the new formatted columns
                        resource_info = {
                            "Region": region,
                            "Service": "AutoScaling",
                            "Resource Name": group["AutoScalingGroupName"],
                            "Resource ID": group["AutoScalingGroupName"],
                            "Launch Configuration": self.format_launch_config(
                                launch_config
                            ),
                            "Min Size": group["MinSize"],
                            "Max Size": group["MaxSize"],
                            "Desired Capacity": group["DesiredCapacity"],
                            "Default Cooldown": group["DefaultCooldown"],
                            "Health Check Type": group["HealthCheckType"],
                            "Health Check Grace Period": group[
                                "HealthCheckGracePeriod"
                            ],
                            "Status": group.get("Status", ""),
                            "Current Size": len(group["Instances"]),
                            **self.format_instances(instances),  # Add instance columns
                            **self.format_scaling_policies(
                                policies
                            ),  # Add policy columns
                            **self.format_scheduled_actions(
                                scheduled_actions
                            ),  # Add action columns
                            "VPC Zone Identifier": group.get("VPCZoneIdentifier", ""),
                            "Termination Policies": ", ".join(
                                group.get("TerminationPolicies", [])
                            ),
                            "New Instances Protected": group.get(
                                "NewInstancesProtectedFromScaleIn", False
                            ),
                            "Service-Linked Role ARN": group.get(
                                "ServiceLinkedRoleARN", ""
                            ),
                            "Tags": ",".join(
                                f"{t.get('Key', '')}={t.get('Value', '')}"
                                for t in group.get("Tags", [])
                            ),
                        }

                        groups.append(resource_info)
                    except ClientError as e:
                        print(
                            f"Error processing Auto Scaling group {group['AutoScalingGroupName']}: {str(e)}"
                        )
                        continue

            return groups
        except ClientError as e:
            print(f"Error getting Auto Scaling resources in {region}: {str(e)}")
            return []
