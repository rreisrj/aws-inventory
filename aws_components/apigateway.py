# aws_components/apigateway.py
from botocore.exceptions import ClientError


class APIGatewayComponent:
    def __init__(self, session):
        self.session = session

    def format_stages(self, stages):
        """Format API stages in a readable way"""
        if not stages:
            return "No stages"

        formatted = []
        for stage in stages:
            stage_info = [
                f"Name: {stage.get('stageName', '')}",
                f"Deployment ID: {stage.get('deploymentId', '')}",
                f"Cache: {'Enabled' if stage.get('cacheClusterEnabled', False) else 'Disabled'}",
                f"Cache Size: {stage.get('cacheClusterSize', 'N/A')}",
                f"Throttling: {'Enabled' if stage.get('throttlingBurstLimit') else 'Disabled'}",
                f"WAF: {stage.get('webAclArn', 'Not configured')}",
                f"Logging: {'Enabled' if stage.get('accessLogSettings', {}) else 'Disabled'}",
            ]
            formatted.append(" | ".join(stage_info))

        return "\n".join(formatted)

    def format_resources_tree(self, resources):
        """Format API resources in a hierarchical tree structure"""
        if not resources:
            return "No resources"

        # Sort resources by path to maintain hierarchy
        sorted_resources = sorted(resources, key=lambda x: x.get("path", ""))

        formatted = []
        for resource in sorted_resources:
            path = resource.get("path", "")
            methods = sorted(resource.get("resourceMethods", {}).keys())

            # Format the resource path
            formatted.append(f"{path}")

            # Add methods
            if methods:
                method_str = f"  ├─ Methods: {', '.join(methods)}"
                formatted.append(method_str)

            # Add parameters if path has them
            if "{" in path:
                params = [param for param in path.split("/") if "{" in param]
                param_str = f"  └─ Parameters: {', '.join(params)}"
                formatted.append(param_str)
            else:
                formatted.append("  └─ Parameters: none")

            # Add empty line between resources
            formatted.append("")

        return "\n".join(formatted[:-1])  # Remove last empty line

    def format_integrations_tree(self, api_id, resources, apigw):
        """Format API integrations in a hierarchical tree structure"""
        if not resources:
            return "No integrations"

        # Sort resources by path to maintain hierarchy
        sorted_resources = sorted(resources, key=lambda x: x.get("path", ""))

        formatted = []
        for resource in sorted_resources:
            path = resource.get("path", "")
            methods = sorted(resource.get("resourceMethods", {}).keys())

            if methods:
                # Add path as header
                formatted.append(f"{path}")

                # Process each method's integration
                for idx, method in enumerate(methods):
                    is_last = idx == len(methods) - 1
                    prefix = "  └─" if is_last else "  ├─"

                    try:
                        integration = apigw.get_integration(
                            restApiId=api_id,
                            resourceId=resource["id"],
                            httpMethod=method,
                        )

                        # Format integration details
                        int_type = integration.get("type", "N/A")
                        int_uri = integration.get("uri", "N/A")
                        if "lambda" in int_uri.lower():
                            # Extract Lambda function name from URI
                            lambda_name = int_uri.split("/")[-1].split(":")[0]
                            int_uri = f"Lambda: {lambda_name}"

                        formatted.extend(
                            [
                                f"{prefix} {method} → {int_uri}",
                                f"  {'   ' if is_last else '  │'} Type: {int_type}",
                                f"  {'   ' if is_last else '  │'} Credentials: {integration.get('credentials', 'N/A')}",
                            ]
                        )

                        # Add method responses if available
                        if integration.get("methodResponses"):
                            formatted.append(
                                f"  {'   ' if is_last else '  │'} Response Codes: {', '.join(integration['methodResponses'].keys())}"
                            )

                    except ClientError:
                        formatted.append(f"{prefix} {method} → No integration found")

                # Add empty line between resources with integrations
                formatted.append("")

        return "\n".join(formatted[:-1])  # Remove last empty line

    def format_httpv2_routes_tree(self, routes, integrations):
        """Format HTTP API routes in a hierarchical tree structure"""
        if not routes:
            return "No routes"

        # Sort routes by route key
        sorted_routes = sorted(routes, key=lambda x: x.get("RouteKey", ""))

        formatted = []
        for route in sorted_routes:
            route_key = route.get("RouteKey", "")
            integration_id = (
                route.get("Target", "").split("/")[-1] if route.get("Target") else None
            )

            # Find matching integration
            integration = (
                next(
                    (i for i in integrations if i["IntegrationId"] == integration_id),
                    {},
                )
                if integration_id
                else {}
            )

            # Format route and integration details
            formatted.extend(
                [
                    f"{route_key}",
                    f"  ├─ Integration Type: {integration.get('IntegrationType', 'N/A')}",
                    f"  ├─ Target: {integration.get('IntegrationUri', 'N/A')}",
                    f"  └─ Response Selection: {integration.get('ResponseSelectionExpression', 'N/A')}",
                    "",
                ]
            )

        return "\n".join(formatted[:-1])  # Remove last empty line

    # [Rest of the component methods remain the same until get_resources]

    def get_resources(self, region):
        """Get API Gateway information"""
        try:
            apigw = self.session.client("apigateway", region_name=region)
            apigwv2 = self.session.client("apigatewayv2", region_name=region)
            resources = []

            # Get REST APIs
            try:
                paginator = apigw.get_paginator("get_rest_apis")
                for page in paginator.paginate():
                    for api in page.get("items", []):
                        try:
                            # Get API resources
                            api_resources = []
                            try:
                                resources_paginator = apigw.get_paginator(
                                    "get_resources"
                                )
                                for resources_page in resources_paginator.paginate(
                                    restApiId=api["id"]
                                ):
                                    api_resources.extend(
                                        resources_page.get("items", [])
                                    )
                            except ClientError as e:
                                print(
                                    f"Error getting resources for API {api['id']}: {str(e)}"
                                )

                            # Get API stages
                            stages = []
                            try:
                                stages_response = apigw.get_stages(restApiId=api["id"])
                                stages = stages_response.get(
                                    "item", []
                                )  # API Gateway uses "item" for stages
                            except ClientError as e:
                                print(
                                    f"Error getting stages for API {api['id']}: {str(e)}"
                                )

                            # Extract API name from tags or use name/id
                            api_name = api.get("name", api["id"])
                            if "tags" in api:
                                api_name = api["tags"].get("Name", api_name)

                            resources.append(
                                {
                                    "Region": region,
                                    "Service": "APIGateway",
                                    "API Type": "REST",
                                    "Resource Name": api_name,
                                    "Resource ID": api["id"],
                                    "Creation Time": str(api.get("createdDate", "")),
                                    "Description": api.get("description", ""),
                                    "Endpoint Type": api.get(
                                        "endpointConfiguration", {}
                                    ).get("types", ["N/A"])[0],
                                    "Protocol": api.get("apiKeySource", "N/A"),
                                    "Resources Structure": self.format_resources_tree(
                                        api_resources
                                    ),
                                    "Integrations Structure": self.format_integrations_tree(
                                        api["id"], api_resources, apigw
                                    ),
                                    "Stages": self.format_stages(stages),
                                    "Tags": ",".join(
                                        f"{k}={v}"
                                        for k, v in api.get("tags", {}).items()
                                    ),
                                }
                            )
                        except ClientError as e:
                            print(f"Error processing REST API {api['id']}: {str(e)}")
                            continue
            except ClientError as e:
                print(f"Error getting REST APIs in {region}: {str(e)}")

            # Get HTTP APIs
            try:
                paginator = apigwv2.get_paginator("get_apis")
                for page in paginator.paginate():
                    for api in page.get("Items", []):
                        try:
                            # Get API routes and integrations
                            routes = []
                            integrations = []

                            try:
                                routes_paginator = apigwv2.get_paginator("get_routes")
                                for routes_page in routes_paginator.paginate(
                                    ApiId=api["ApiId"]
                                ):
                                    routes.extend(routes_page.get("Items", []))
                            except ClientError as e:
                                print(
                                    f"Error getting routes for HTTP API {api['ApiId']}: {str(e)}"
                                )

                            try:
                                integrations_paginator = apigwv2.get_paginator(
                                    "get_integrations"
                                )
                                for (
                                    integrations_page
                                ) in integrations_paginator.paginate(
                                    ApiId=api["ApiId"]
                                ):
                                    integrations.extend(
                                        integrations_page.get("Items", [])
                                    )
                            except ClientError as e:
                                print(
                                    f"Error getting integrations for HTTP API {api['ApiId']}: {str(e)}"
                                )

                            # Get API stages
                            stages = []
                            try:
                                stages_paginator = apigwv2.get_paginator("get_stages")
                                for stages_page in stages_paginator.paginate(
                                    ApiId=api["ApiId"]
                                ):
                                    stages.extend(stages_page.get("Items", []))
                            except ClientError as e:
                                print(
                                    f"Error getting stages for HTTP API {api['ApiId']}: {str(e)}"
                                )

                            resources.append(
                                {
                                    "Region": region,
                                    "Service": "APIGateway",
                                    "API Type": "HTTP",
                                    "Resource Name": api.get("Name", api["ApiId"]),
                                    "Resource ID": api["ApiId"],
                                    "Creation Time": str(api.get("CreatedDate", "")),
                                    "Description": api.get("Description", ""),
                                    "Protocol": api.get("ProtocolType", "N/A"),
                                    "Routes Structure": self.format_httpv2_routes_tree(
                                        routes, integrations
                                    ),
                                    "Stages": self.format_stages(stages),
                                    "Tags": ",".join(
                                        f"{k}={v}"
                                        for k, v in api.get("Tags", {}).items()
                                    ),
                                }
                            )
                        except ClientError as e:
                            print(f"Error processing HTTP API {api['ApiId']}: {str(e)}")
                            continue
            except ClientError as e:
                print(f"Error getting HTTP APIs in {region}: {str(e)}")

            return resources
        except ClientError as e:
            print(f"Error getting API Gateway resources in {region}: {str(e)}")
            return []
