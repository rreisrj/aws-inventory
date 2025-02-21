# aws_components/ecr.py
from botocore.exceptions import ClientError


class ECRComponent:
    def __init__(self, session):
        self.session = session

    def get_resources(self, region):
        """Get ECR repositories information"""
        try:
            ecr = self.session.client("ecr", region_name=region)
            repositories = []

            paginator = ecr.get_paginator("describe_repositories")
            for page in paginator.paginate():
                for repo in page["repositories"]:
                    # Get repository tags
                    try:
                        tags = ecr.list_tags_for_resource(
                            resourceArn=repo["repositoryArn"]
                        )["tags"]
                    except ClientError:
                        tags = []

                    # Get repository policy
                    try:
                        policy = ecr.get_repository_policy(
                            repositoryName=repo["repositoryName"]
                        )
                        policy_text = policy.get("policyText", "{}")
                    except ClientError:
                        policy_text = "{}"

                    # Get lifecycle policy
                    try:
                        lifecycle = ecr.get_lifecycle_policy(
                            repositoryName=repo["repositoryName"]
                        )
                        lifecycle_policy = lifecycle.get("lifecyclePolicyText", "{}")
                    except ClientError:
                        lifecycle_policy = "{}"

                    # Get image details
                    images = []
                    try:
                        image_paginator = ecr.get_paginator("describe_images")
                        for image_page in image_paginator.paginate(
                            repositoryName=repo["repositoryName"]
                        ):
                            for image in image_page["imageDetails"]:
                                images.append(
                                    {
                                        "ImageTags": image.get("imageTags", []),
                                        "PushedAt": str(image.get("imagePushedAt", "")),
                                        "Size": image.get("imageSizeInBytes", 0),
                                        "Digest": image.get("imageDigest", ""),
                                    }
                                )
                    except ClientError:
                        pass

                    repositories.append(
                        {
                            "Region": region,
                            "Service": "ECR",
                            "Resource Name": repo.get("repositoryName", ""),
                            "Resource ID": repo.get("repositoryArn", ""),
                            "Registry ID": repo.get("registryId", ""),
                            "Created At": str(repo.get("createdAt", "")),
                            "URI": repo.get("repositoryUri", ""),
                            "Image Tag Mutability": repo.get("imageTagMutability", ""),
                            "Scan on Push": repo.get(
                                "imageScanningConfiguration", {}
                            ).get("scanOnPush", False),
                            "Encryption Type": repo.get(
                                "encryptionConfiguration", {}
                            ).get("encryptionType", "AES256"),
                            "Policy": policy_text,
                            "Lifecycle Policy": lifecycle_policy,
                            "Image Count": len(images),
                            "Latest Images": str(
                                images[:5] if images else []
                            ),  # Show only last 5 images
                            "Tags": str(tags),
                        }
                    )

            return repositories
        except ClientError as e:
            print(f"Error getting ECR resources in {region}: {str(e)}")
            return []
