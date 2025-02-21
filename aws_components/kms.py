# aws_components/kms.py
import json

from botocore.exceptions import ClientError


class KMSComponent:
    def __init__(self, session):
        self.session = session

    def format_key_policy(self, policy):
        """Format key policy in proper JSON format"""
        if not policy:
            return "{}"

        try:
            # If policy is already a dict, convert to formatted JSON string
            if isinstance(policy, dict):
                return json.dumps(policy, indent=2)
            # If policy is a string, parse it and format
            return json.dumps(json.loads(policy), indent=2)
        except (json.JSONDecodeError, TypeError):
            return str(policy)

    def get_resources(self, region):
        """Get KMS keys information including aliases and policies"""
        try:
            kms = self.session.client("kms", region_name=region)
            keys = []

            # Get list of keys
            paginator = kms.get_paginator("list_keys")
            for page in paginator.paginate():
                for key in page["Keys"]:
                    try:
                        # Get detailed key information
                        key_info = kms.describe_key(KeyId=key["KeyId"])["KeyMetadata"]

                        # Get key aliases
                        aliases = []
                        try:
                            alias_paginator = kms.get_paginator("list_aliases")
                            for alias_page in alias_paginator.paginate(
                                KeyId=key["KeyId"]
                            ):
                                for alias in alias_page["Aliases"]:
                                    aliases.append(alias["AliasName"])
                        except ClientError:
                            pass

                        # Get key tags
                        tags = []
                        try:
                            tag_response = kms.list_resource_tags(KeyId=key["KeyId"])
                            tags = tag_response.get("Tags", [])
                        except ClientError:
                            pass

                        # Get rotation status
                        rotation_status = "N/A"
                        try:
                            if (
                                key_info["KeyManager"] == "CUSTOMER"
                            ):  # Only customer-managed keys support rotation
                                rotation = kms.get_key_rotation_status(
                                    KeyId=key["KeyId"]
                                )
                                rotation_status = (
                                    "Enabled"
                                    if rotation["KeyRotationEnabled"]
                                    else "Disabled"
                                )
                        except ClientError:
                            pass

                        # Get key policy
                        policy = "N/A"
                        try:
                            policy_response = kms.get_key_policy(
                                KeyId=key["KeyId"], PolicyName="default"
                            )
                            policy = policy_response["Policy"]
                        except ClientError:
                            pass

                        # Get key grants
                        grants = []
                        try:
                            grant_paginator = kms.get_paginator("list_grants")
                            for grant_page in grant_paginator.paginate(
                                KeyId=key["KeyId"]
                            ):
                                for grant in grant_page["Grants"]:
                                    grants.append(
                                        {
                                            "GrantId": grant.get("GrantId", ""),
                                            "GranteePrincipal": grant.get(
                                                "GranteePrincipal", ""
                                            ),
                                            "Operations": grant.get("Operations", []),
                                        }
                                    )
                        except ClientError:
                            pass

                        # Format key usage
                        key_usage = key_info.get("KeyUsage", "N/A")
                        if key_usage == "ENCRYPT_DECRYPT":
                            encryption_algorithms = key_info.get(
                                "EncryptionAlgorithms", ["N/A"]
                            )
                            key_usage = (
                                f"{key_usage} ({', '.join(encryption_algorithms)})"
                            )
                        elif key_usage == "SIGN_VERIFY":
                            signing_algorithms = key_info.get(
                                "SigningAlgorithms", ["N/A"]
                            )
                            key_usage = f"{key_usage} ({', '.join(signing_algorithms)})"

                        keys.append(
                            {
                                "Region": region,
                                "Service": "KMS",
                                "Resource Name": (
                                    aliases[0] if aliases else key["KeyId"]
                                ),
                                "Resource ID": key["KeyId"],
                                "ARN": key_info["Arn"],
                                "Description": key_info.get("Description", ""),
                                "Enabled": key_info["Enabled"],
                                "Key State": key_info["KeyState"],
                                "Key Manager": key_info["KeyManager"],
                                "Creation Date": str(key_info["CreationDate"]),
                                "Key Usage": key_usage,
                                "Origin": key_info["Origin"],
                                "Custom Key Store": key_info.get(
                                    "CustomKeyStoreId", "N/A"
                                ),
                                "Key Spec": key_info.get(
                                    "CustomerMasterKeySpec",
                                    key_info.get("KeySpec", "N/A"),
                                ),
                                "Deletion Date": str(
                                    key_info.get("DeletionDate", "N/A")
                                ),
                                "Valid To": str(key_info.get("ValidTo", "N/A")),
                                "Aliases": (
                                    " | ".join(aliases) if aliases else "No aliases"
                                ),
                                "Tags": str(tags),
                                "Key Rotation": rotation_status,
                                "Multi-Region": key_info.get("MultiRegion", False),
                                "Multi-Region Type": key_info.get(
                                    "MultiRegionConfiguration", {}
                                ).get("MultiRegionKeyType", "N/A"),
                                "Primary Region": key_info.get(
                                    "MultiRegionConfiguration", {}
                                )
                                .get("PrimaryKey", {})
                                .get("Region", "N/A"),
                                "Replica Regions": str(
                                    [
                                        r["Region"]
                                        for r in key_info.get(
                                            "MultiRegionConfiguration", {}
                                        ).get("ReplicaKeys", [])
                                    ]
                                ),
                                "Grant Count": len(grants),
                                "Grants": str(grants) if grants else "No grants",
                                "Key Policy": self.format_key_policy(policy),
                            }
                        )
                    except ClientError as e:
                        print(f"Error processing key {key['KeyId']}: {str(e)}")
                        continue

            return keys
        except ClientError as e:
            print(f"Error getting KMS resources in {region}: {str(e)}")
            return []
