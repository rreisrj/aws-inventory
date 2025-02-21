# aws_components/ecs.py
from botocore.exceptions import ClientError


class ECSComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get ECS clusters, services, and tasks information"""
        try:
            ecs = self.session.client("ecs", region_name=region)
            clusters = []

            # Get list of clusters
            paginator = ecs.get_paginator("list_clusters")
            for page in paginator.paginate():
                if not page["clusterArns"]:
                    continue

                # Get detailed cluster information
                cluster_details = ecs.describe_clusters(
                    clusters=page["clusterArns"],
                    include=["TAGS", "CONFIGURATIONS", "SETTINGS"],
                )["clusters"]

                for cluster in cluster_details:
                    # Get services in cluster
                    services = []
                    try:
                        service_paginator = ecs.get_paginator("list_services")
                        for service_page in service_paginator.paginate(
                            cluster=cluster["clusterArn"]
                        ):
                            if not service_page["serviceArns"]:
                                continue

                            service_details = ecs.describe_services(
                                cluster=cluster["clusterArn"],
                                services=service_page["serviceArns"],
                            )["services"]

                            for service in service_details:
                                services.append(
                                    {
                                        "ServiceName": service.get("serviceName", ""),
                                        "Status": service.get("status", ""),
                                        "DesiredCount": service.get("desiredCount", 0),
                                        "RunningCount": service.get("runningCount", 0),
                                        "PendingCount": service.get("pendingCount", 0),
                                        "LaunchType": service.get("launchType", ""),
                                        "TaskDefinition": service.get(
                                            "taskDefinition", ""
                                        ),
                                        "LoadBalancers": str(
                                            service.get("loadBalancers", [])
                                        ),
                                        "NetworkConfiguration": str(
                                            service.get("networkConfiguration", {})
                                        ),
                                    }
                                )
                    except ClientError:
                        pass

                    # Get container instances
                    container_instances = []
                    try:
                        instance_paginator = ecs.get_paginator(
                            "list_container_instances"
                        )
                        for instance_page in instance_paginator.paginate(
                            cluster=cluster["clusterArn"]
                        ):
                            if not instance_page["containerInstanceArns"]:
                                continue

                            instance_details = ecs.describe_container_instances(
                                cluster=cluster["clusterArn"],
                                containerInstances=instance_page[
                                    "containerInstanceArns"
                                ],
                            )["containerInstances"]

                            for instance in instance_details:
                                container_instances.append(
                                    {
                                        "EC2InstanceId": instance.get(
                                            "ec2InstanceId", ""
                                        ),
                                        "Status": instance.get("status", ""),
                                        "RunningTasksCount": instance.get(
                                            "runningTasksCount", 0
                                        ),
                                        "PendingTasksCount": instance.get(
                                            "pendingTasksCount", 0
                                        ),
                                        "AgentConnected": instance.get(
                                            "agentConnected", False
                                        ),
                                        "CapacityProvider": instance.get(
                                            "capacityProviderName", ""
                                        ),
                                    }
                                )
                    except ClientError:
                        pass

                    # Get tasks
                    tasks = []
                    try:
                        task_paginator = ecs.get_paginator("list_tasks")
                        for task_page in task_paginator.paginate(
                            cluster=cluster["clusterArn"]
                        ):
                            if not task_page["taskArns"]:
                                continue

                            task_details = ecs.describe_tasks(
                                cluster=cluster["clusterArn"],
                                tasks=task_page["taskArns"],
                            )["tasks"]

                            for task in task_details:
                                tasks.append(
                                    {
                                        "TaskArn": task.get("taskArn", ""),
                                        "LastStatus": task.get("lastStatus", ""),
                                        "DesiredStatus": task.get("desiredStatus", ""),
                                        "LaunchType": task.get("launchType", ""),
                                        "ContainerInstanceArn": task.get(
                                            "containerInstanceArn", ""
                                        ),
                                        "Group": task.get("group", ""),
                                        "Containers": str(
                                            [
                                                {
                                                    "Name": c.get("name", ""),
                                                    "Status": c.get("lastStatus", ""),
                                                }
                                                for c in task.get("containers", [])
                                            ]
                                        ),
                                    }
                                )
                    except ClientError:
                        pass

                    clusters.append(
                        {
                            "Region": region,
                            "Service": "ECS",
                            "Resource Name": cluster.get("clusterName", ""),
                            "Resource ID": cluster.get("clusterArn", ""),
                            "Status": cluster.get("status", ""),
                            "Active Services Count": len(services),
                            "Active Tasks Count": len(tasks),
                            "Container Instances Count": len(container_instances),
                            "Registered Container Instances": str(container_instances),
                            "Services": str(services),
                            "Tasks": str(tasks),
                            "Default Capacity Provider Strategy": str(
                                cluster.get("defaultCapacityProviderStrategy", [])
                            ),
                            "Settings": str(cluster.get("settings", [])),
                            "Tags": str(cluster.get("tags", [])),
                            "Statistics": str(cluster.get("statistics", [])),
                        }
                    )

            return clusters
        except ClientError as e:
            print(f"Error getting ECS resources in {region}: {str(e)}")
            return []
