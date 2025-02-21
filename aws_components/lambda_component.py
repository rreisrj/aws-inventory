# aws_components/lambda_component.py
import json

from botocore.exceptions import ClientError


class LambdaComponent:
    def __init__(self, session):
        self.session = session

    def format_code_size_mb(self, size_bytes):
        """Convert bytes to megabytes with 2 decimal places"""
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    def format_vpc_config(self, vpc_config):
        """Format VPC configuration in a readable way"""
        if not vpc_config:
            return {"VPC ID": "", "Subnet IDs": "", "Security Group IDs": ""}

        return {
            "VPC ID": vpc_config.get("VpcId", ""),
            "Subnet IDs": "; ".join(vpc_config.get("SubnetIds", [])),
            "Security Group IDs": "; ".join(vpc_config.get("SecurityGroupIds", [])),
        }

    def format_triggers(self, function_name, lambda_client):
        """Format Lambda triggers in a readable way"""
        try:
            policy = lambda_client.get_policy(FunctionName=function_name)
            policy_json = json.loads(policy["Policy"])

            triggers = []
            for statement in policy_json.get("Statement", []):
                principal = statement.get("Principal", {})
                if isinstance(principal, dict):
                    service = principal.get("Service", "")
                else:
                    service = principal

                source_arn = (
                    statement.get("Condition", {})
                    .get("ArnLike", {})
                    .get("AWS:SourceArn", "")
                )
                if source_arn:
                    triggers.append(f"{service}:{source_arn.split(':')[-1]}")
                else:
                    triggers.append(service)

            return "; ".join(triggers) if triggers else "No triggers"
        except ClientError:
            return "No triggers"

    def get_resources(self, region):
        """Get Lambda functions information"""
        try:
            lambda_client = self.session.client("lambda", region_name=region)
            functions = []

            paginator = lambda_client.get_paginator("list_functions")
            for page in paginator.paginate():
                for function in page["Functions"]:
                    # Get function tags
                    try:
                        tags = lambda_client.list_tags(
                            Resource=function["FunctionArn"]
                        )["Tags"]
                    except ClientError:
                        tags = {}

                    # Get reserved concurrency configuration
                    reserved_concurrency = "Not configured"
                    try:
                        concurrency = lambda_client.get_function_concurrency(
                            FunctionName=function["FunctionName"]
                        )
                        if "ReservedConcurrentExecutions" in concurrency:
                            reserved_concurrency = str(
                                concurrency["ReservedConcurrentExecutions"]
                            )
                    except ClientError:
                        pass

                    # Get function triggers/event sources
                    triggers = []
                    try:
                        event_configs = lambda_client.list_event_source_mappings(
                            FunctionName=function["FunctionName"]
                        )
                        for event in event_configs.get("EventSourceMappings", []):
                            triggers.append(
                                {
                                    "Source": event.get("EventSourceArn", ""),
                                    "State": event.get("State", ""),
                                    "Type": "Event Source Mapping",
                                }
                            )
                    except ClientError:
                        pass

                    # Get function policy (triggers from other AWS services)
                    try:
                        policy = lambda_client.get_policy(
                            FunctionName=function["FunctionName"]
                        )
                        if policy and "Policy" in policy:
                            policy_dict = json.loads(policy["Policy"])
                            for statement in policy_dict.get("Statement", []):
                                triggers.append(
                                    {
                                        "Source": statement.get("Principal", {}).get(
                                            "Service", ""
                                        ),
                                        "Action": statement.get("Action", ""),
                                        "Type": "Service Integration",
                                    }
                                )
                    except ClientError:
                        # Function might not have a resource policy
                        pass

                    # Format VPC config
                    vpc_info = self.format_vpc_config(function.get("VpcConfig", {}))

                    # Get and format triggers
                    triggers_str = self.format_triggers(
                        function["FunctionName"], lambda_client
                    )

                    functions.append(
                        {
                            "Region": region,
                            "Service": "Lambda",
                            "Resource Name": function.get("FunctionName", ""),
                            "Resource ID": function.get("FunctionArn", ""),
                            "Runtime": function.get("Runtime", ""),
                            "Handler": function.get("Handler", ""),
                            "Role": function.get("Role", ""),
                            "Memory": function.get("MemorySize", ""),
                            "Timeout": function.get("Timeout", ""),
                            "Last Modified": str(function.get("LastModified", "")),
                            "Code Size": self.format_code_size_mb(
                                function.get("CodeSize", 0)
                            ),
                            "Reserved Concurrency": reserved_concurrency,
                            "Description": function.get("Description", ""),
                            "Environment": str(
                                function.get("Environment", {}).get("Variables", {})
                            ),
                            **vpc_info,  # Add formatted VPC config columns
                            "Triggers": triggers_str,
                            "Tags": str(tags),
                            "Architecture": function.get("Architectures", ["x86_64"])[
                                0
                            ],
                            "State": function.get("State", ""),
                            "StateReason": function.get("StateReason", ""),
                            "Layers": str(
                                [
                                    layer.get("Arn", "")
                                    for layer in function.get("Layers", [])
                                ]
                            ),
                        }
                    )

            return functions
        except ClientError as e:
            print(f"Error getting Lambda resources in {region}: {str(e)}")
            return []
