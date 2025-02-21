# aws_components/eks.py
from botocore.exceptions import ClientError


class EKSComponent:
    def __init__(self, session):
        self.session = session

    def format_fargate_profiles(self, profiles):
        """Format Fargate profiles with line breaks"""
        if not profiles:
            return "No Fargate profiles"

        formatted = []
        for profile in profiles:
            profile_str = [
                f"Profile: {profile['name']}",
                f"  - Status: {profile['status']}",
                f"  - Pod Execution Role: {profile.get('podExecutionRoleArn', 'N/A')}",
            ]

            # Add selectors
            if profile.get("selectors"):
                profile_str.append("  - Selectors:")
                for selector in profile["selectors"]:
                    profile_str.append(
                        "    • Namespace: " + selector.get("namespace", "N/A")
                    )
                    if selector.get("labels"):
                        for key, value in selector["labels"].items():
                            profile_str.append(f"      - Label: {key}={value}")

            # Add subnets
            if profile.get("subnets"):
                profile_str.append("  - Subnets:")
                for subnet in profile["subnets"]:
                    profile_str.append(f"    • {subnet}")

            formatted.append("\n".join(profile_str))

        return "\n\n".join(formatted)

    def check_managed_node_groups_auto_mode(self, eks, cluster_name):
        """Check if EKS managed node groups have auto mode enabled"""
        try:
            # Get cluster's node groups
            response = eks.list_nodegroups(clusterName=cluster_name)
            auto_mode_status = []

            for ng_name in response.get("nodegroups", []):
                ng_details = eks.describe_nodegroup(
                    clusterName=cluster_name, nodegroupName=ng_name
                )["nodegroup"]

                # Check for auto scaling configuration
                auto_scaling = ng_details.get("scalingConfig", {})
                update_config = ng_details.get("updateConfig", {})

                auto_mode_info = {
                    "name": ng_name,
                    "auto_scaling": bool(auto_scaling),
                    "max_unavailable": update_config.get("maxUnavailable"),
                    "max_unavailable_percentage": update_config.get(
                        "maxUnavailablePercentage"
                    ),
                }
                auto_mode_status.append(auto_mode_info)

            return auto_mode_status
        except ClientError as e:
            print(f"Error checking auto mode for cluster {cluster_name}: {str(e)}")
            return []

    def format_auto_mode_status(self, auto_mode_status):
        """Format auto mode status with line breaks"""
        if not auto_mode_status:
            return "Auto Mode information not available"

        formatted = ["Auto Mode Configuration:"]
        for ng in auto_mode_status:
            ng_str = [
                f"  - Nodegroup: {ng['name']}",
                f"    • Auto Scaling: {'Enabled' if ng['auto_scaling'] else 'Disabled'}",
            ]

            if ng["max_unavailable"]:
                ng_str.append(f"    • Max Unavailable: {ng['max_unavailable']}")
            if ng["max_unavailable_percentage"]:
                ng_str.append(
                    f"    • Max Unavailable Percentage: {ng['max_unavailable_percentage']}%"
                )

            formatted.extend(ng_str)

        return "\n".join(formatted)

    def get_resources(self, region):
        """Get EKS clusters information"""
        try:
            eks = self.session.client("eks", region_name=region)
            ec2 = self.session.client("ec2", region_name=region)
            clusters = []

            try:
                paginator = eks.get_paginator("list_clusters")
                for page in paginator.paginate():
                    for cluster_name in page["clusters"]:
                        try:
                            # Get detailed cluster information
                            cluster = eks.describe_cluster(name=cluster_name)["cluster"]

                            # Get Fargate profiles
                            fargate_profiles = []
                            try:
                                fp_paginator = eks.get_paginator(
                                    "list_fargate_profiles"
                                )
                                for fp_page in fp_paginator.paginate(
                                    clusterName=cluster_name
                                ):
                                    for profile_name in fp_page["fargateProfileNames"]:
                                        profile = eks.describe_fargate_profile(
                                            clusterName=cluster_name,
                                            fargateProfileName=profile_name,
                                        )["fargateProfile"]
                                        fargate_profiles.append(profile)
                            except ClientError:
                                pass

                            # Check Auto Mode status
                            auto_mode_status = self.check_managed_node_groups_auto_mode(
                                eks, cluster_name
                            )

                            # Get nodegroups information
                            nodegroups = []
                            try:
                                ng_paginator = eks.get_paginator("list_nodegroups")
                                for ng_page in ng_paginator.paginate(
                                    clusterName=cluster_name
                                ):
                                    nodegroups.extend(ng_page["nodegroups"])
                            except ClientError:
                                pass

                            clusters.append(
                                {
                                    "Region": region,
                                    "Service": "EKS",
                                    "Resource Name": cluster["name"],
                                    "Resource ID": cluster["arn"],
                                    "Version": cluster["version"],
                                    "Status": cluster["status"],
                                    "Endpoint": cluster["endpoint"],
                                    "Role ARN": cluster["roleArn"],
                                    "VPC ID": cluster["resourcesVpcConfig"]["vpcId"],
                                    "Subnets": str(
                                        cluster["resourcesVpcConfig"]["subnetIds"]
                                    ),
                                    "Security Groups": str(
                                        cluster["resourcesVpcConfig"][
                                            "securityGroupIds"
                                        ]
                                    ),
                                    "Cluster Security Group": cluster[
                                        "resourcesVpcConfig"
                                    ].get("clusterSecurityGroupId", "N/A"),
                                    "Logging Types": str(
                                        cluster.get("logging", {}).get(
                                            "clusterLogging", []
                                        )
                                    ),
                                    "Kubernetes Network Config": str(
                                        cluster.get("kubernetesNetworkConfig", {})
                                    ),
                                    "Node Groups": str(nodegroups),
                                    "Fargate Profiles": self.format_fargate_profiles(
                                        fargate_profiles
                                    ),
                                    "Auto Mode Status": self.format_auto_mode_status(
                                        auto_mode_status
                                    ),
                                    "Fargate Enabled": (
                                        "Yes" if fargate_profiles else "No"
                                    ),
                                    "Tags": str(cluster.get("tags", {})),
                                }
                            )
                        except ClientError as e:
                            print(f"Error processing cluster {cluster_name}: {str(e)}")
                            continue
            except ClientError as e:
                print(f"Error listing clusters in {region}: {str(e)}")

            return clusters
        except ClientError as e:
            print(f"Error getting EKS resources in {region}: {str(e)}")
            return []
