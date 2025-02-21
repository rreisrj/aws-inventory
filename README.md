# AWS Resource Inventory Tool v1.0

A powerful Python-based tool for collecting and documenting AWS resources across multiple regions. This tool generates detailed Excel reports of your AWS infrastructure, supporting parallel processing and customizable resource collection.

## Features

- **Multi-Region Support**: Scan AWS resources across multiple regions simultaneously
- **Parallel Processing**: Efficiently collect resources using parallel execution
- **Selective Scanning**: Choose specific services to scan or scan all supported services
- **Rich Excel Output**: Generate detailed Excel reports with:
  - Summary sheet showing resource counts by service and region
  - Detailed sheets for each service with comprehensive resource information
  - Critical information highlighted and properly formatted
  - Automatic column width adjustment for better readability

## Supported Services

- API Gateway (REST and HTTP APIs)
- Auto Scaling Groups
- DynamoDB
- CloudFront
- EC2 Resources
- ECR Repositories
- ECS Clusters
- EFS File Systems
- EKS Clusters
- Elastic Load Balancers
- API Gateway
- KMS Keys
- Lambda Functions
- RDS Instances
- Route53 Resources
- S3 Buckets
- SNS Topics
- SQS Queues
- Unattached Resources (EBS, Security Groups, EIPs, ENIs)
- VPC Resources

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rreisrj/aws-inventory.git
   cd aws-inventory
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Authentication

The tool supports multiple authentication methods:

1. **AWS CLI Profiles**:
   - Configure your AWS credentials using `aws configure`
   - The tool will automatically list and let you select available profiles
   - Supports both credentials file (`~/.aws/credentials`) and config file (`~/.aws/config`)

2. **Environment Variables**:
   - Set AWS credentials via environment variables:
     ```bash
     export AWS_ACCESS_KEY_ID="your_access_key"
     export AWS_SECRET_ACCESS_KEY="your_secret_key"
     export AWS_SESSION_TOKEN="your_session_token"  # If using temporary credentials
     ```

## Usage

1. Run the tool:
   ```bash
   python aws_service_summary.py
   ```

2. Follow the interactive prompts to:
   - Select an AWS profile
   - Choose regions to scan
   - Select services to inventory (all or specific services)

3. The tool will generate an Excel file named `aws_inventory_<account-id>_<timestamp>.xlsx`

## Project Structure

```
aws_inventory/
├── aws_components/           # Service-specific components
│   ├── __init__.py          # Component initialization
│   ├── apigateway.py        # API Gateway component
│   ├── autoscaling.py       # Auto Scaling component
│   └── ...                  # Other service components
├── aws_service_summary.py    # Main application file
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Adding New Service Components

1. Create a new component file in `aws_components/`:
   ```python
   # aws_components/new_service.py
   from botocore.exceptions import ClientError

   class NewServiceComponent:
       def __init__(self, session):
           self.session = session

       def get_resources(self, region):
           """Get resources for the new service"""
           try:
               client = self.session.client("service-name", region_name=region)
               resources = []

               # Collect resources here
               # Each resource should be a dictionary with at least:
               # - Region
               # - Service
               # - Resource Name
               # - Resource ID

               return resources
           except ClientError as e:
               print(f"Error getting resources in {region}: {str(e)}")
               return []
   ```

2. Update `aws_components/__init__.py`:
   ```python
   from .new_service import NewServiceComponent

   def initialize_all_components(session):
       components = {
           # ... existing components ...
           "NewService": NewServiceComponent(session),
       }
       return components
   ```

3. Add the service name to `supported_services` in `aws_service_summary.py`

## Best Practices for Component Development

1. **Error Handling**:
   - Always use try-except blocks for AWS API calls
   - Log errors with meaningful messages
   - Return empty list on failure to maintain resilience

2. **Resource Format**:
   - Include all critical fields:
     - Region
     - Service
     - Resource Name
     - Resource ID
     - Description (if available)
     - Creation Time (if available)

3. **Performance**:
   - Use pagination for AWS API calls that support it
   - Format data efficiently
   - Add proper error handling

4. **Documentation**:
   - Add docstrings to all methods
   - Document any special handling or assumptions
   - Include example resource format

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License

## Support

For issues, questions, or contributions, please create an issue or contact the maintainers.
