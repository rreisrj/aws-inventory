# aws_components/cloudfront.py
from botocore.exceptions import ClientError


class CloudFrontComponent:
    def __init__(self, session):
        self.session = session

    def format_origins(self, origins):
        """Format origins in a readable way"""
        if not origins:
            return "No origins"

        formatted = []
        for origin in origins.get("Items", []):
            origin_info = [
                f"ID: {origin.get('Id', '')}",
                f"Domain: {origin.get('DomainName', '')}",
                f"Path: {origin.get('OriginPath', '/')}",
            ]

            # Add S3 origin config if exists
            if "S3OriginConfig" in origin:
                origin_info.append(f"Type: S3")
                origin_info.append(
                    f"OAI: {origin['S3OriginConfig'].get('OriginAccessIdentity', 'None')}"
                )

            # Add custom origin config if exists
            if "CustomOriginConfig" in origin:
                config = origin["CustomOriginConfig"]
                origin_info.extend(
                    [
                        f"Type: Custom",
                        f"Protocol: {config.get('OriginProtocolPolicy', '')}",
                        f"HTTP Port: {config.get('HTTPPort', '')}",
                        f"HTTPS Port: {config.get('HTTPSPort', '')}",
                    ]
                )

            formatted.append(" | ".join(origin_info))

        return "\n".join(formatted)

    def format_behaviors(self, behaviors):
        """Format cache behaviors in a readable way"""
        if not behaviors:
            return "No behaviors"

        formatted = []
        for behavior in behaviors.get("Items", []):
            if not behavior:  # Skip empty behaviors
                continue
            behavior_info = [
                f"Path: {behavior.get('PathPattern', '*')}",
                f"Target Origin: {behavior.get('TargetOriginId', '')}",
                f"Viewer Protocol: {behavior.get('ViewerProtocolPolicy', '')}",
                f"Allowed Methods: {','.join(behavior.get('AllowedMethods', {}).get('Items', []))}",
            ]
            formatted.append(" | ".join(behavior_info))

        return "\n".join(formatted) if formatted else "No behaviors"

    def get_resources(self, region):
        """Get CloudFront distributions information"""
        resources = []
        try:
            # CloudFront is a global service, we'll use us-east-1 as the primary region
            cloudfront = self.session.client("cloudfront", region_name="us-east-1")

            try:
                # Get list of distributions
                response = cloudfront.list_distributions()
                distribution_list = response.get("DistributionList", {})

                if not distribution_list:
                    print(f"No CloudFront distributions found")
                    return resources

                items = distribution_list.get("Items", [])
                if not items:
                    print(f"No CloudFront distributions found")
                    return resources

                print(f"Found {len(items)} CloudFront distributions")

                for dist in items:
                    # Get tags for this distribution
                    tags = []
                    try:
                        tag_response = cloudfront.list_tags_for_resource(
                            Resource=dist["ARN"]
                        )
                        tags = tag_response.get("Tags", {}).get("Items", [])
                    except ClientError as e:
                        print(
                            f"Warning: Could not fetch tags for distribution {dist['Id']}: {str(e)}"
                        )

                    # Get detailed configuration
                    config = {}
                    try:
                        detail = cloudfront.get_distribution(Id=dist["Id"])
                        if "Distribution" in detail:
                            config = detail["Distribution"].get(
                                "DistributionConfig", {}
                            )
                    except ClientError as e:
                        print(
                            f"Warning: Could not fetch details for distribution {dist['Id']}: {str(e)}"
                        )
                        continue

                    # Determine operational status
                    is_enabled = dist.get("Enabled", False)
                    status = dist.get("Status", "")
                    operational_status = (
                        "Running"
                        if is_enabled and status == "Deployed"
                        else "Not Running"
                    )

                    resources.append(
                        {
                            "Region": region,
                            "Service": "CloudFront",
                            "Type": "Distribution",
                            "Resource Name": dist.get("DomainName", ""),
                            "Resource ID": dist["Id"],
                            "ARN": dist.get("ARN", ""),
                            "Status": operational_status,
                            "Distribution Status": status,
                            "Enabled": str(is_enabled),
                            "Origins": self.format_origins(config.get("Origins", {})),
                            "Default Cache Behavior": self.format_behaviors(
                                {"Items": [config.get("DefaultCacheBehavior", {})]}
                                if config.get("DefaultCacheBehavior")
                                else {}
                            ),
                            "Cache Behaviors": self.format_behaviors(
                                config.get("CacheBehaviors", {})
                            ),
                            "Custom Error Responses": str(
                                config.get("CustomErrorResponses", {}).get("Items", [])
                            ),
                            "Comment": config.get("Comment", ""),
                            "Price Class": config.get("PriceClass", ""),
                            "Aliases": ",".join(
                                config.get("Aliases", {}).get("Items", [])
                            ),
                            "SSL Certificate": config.get("ViewerCertificate", {}).get(
                                "ACMCertificateArn",
                                config.get("ViewerCertificate", {}).get(
                                    "IAMCertificateId", "Default"
                                ),
                            ),
                            "SSL Support Method": config.get(
                                "ViewerCertificate", {}
                            ).get("SSLSupportMethod", "N/A"),
                            "Logging": str(config.get("Logging", {})),
                            "Web ACL": config.get("WebACLId", "None"),
                            "HTTP Version": config.get("HttpVersion", ""),
                            "IPv6 Enabled": str(config.get("IsIPV6Enabled", False)),
                            "Last Modified": str(dist.get("LastModifiedTime", "")),
                            "Tags": str([{t["Key"]: t["Value"]} for t in tags]),
                        }
                    )

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "NoSuchDistribution":
                    print(f"No CloudFront distributions found")
                else:
                    print(f"Error listing CloudFront distributions: {str(e)}")
                return resources

        except Exception as e:
            print(f"Error initializing CloudFront client: {str(e)}")
            return resources

        return resources
