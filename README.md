# AWS Cleaner GUI Tool

A GUI-based utility to safely clean up AWS resources across multiple accounts and regions.

## Features

- Select from multiple AWS profiles configured in your credentials file
- Choose which AWS resource types to clean up:
  - EC2 (instances, volumes, snapshots, AMIs, etc.)
  - S3 (buckets and objects)
  - Lambda (functions and layers)
  - CloudFormation (stacks)
  - RDS (instances, clusters, snapshots)
  - VPC (subnets, route tables, gateways, etc.)
  - IAM (users, roles, policies)
- Automatic region detection and resource cleanup
- Dry run mode to preview changes without modifying resources
- Detailed logging of all operations

## Logging

- Detailed logs are displayed in the GUI interface (INFO level)
- The log file `aws_cleanup.log` only records:
  - Successful resource deletion operations
  - Warnings
  - Errors
- This focused logging helps identify exactly what resources were modified
- You can review the log file to see all resources that were successfully deleted

## Prerequisites

- Python 3.8+
- AWS CLI configured with credential profiles
- Boto3 library
- Tkinter (usually comes with Python, but may need separate installation on some systems)

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/aws-cleaner.git
cd aws-cleaner
```

2. Install dependencies:

```bash
pip install boto3
```

## Usage

1. Run the application:

```bash
python aws_cleaner/aws_cleanup_gui.py
```

2. Select an AWS profile from the dropdown
3. Check the resource types you want to clean
4. Enable "Dry Run" mode to safely review what would be deleted (recommended)
5. Click "Start Cleanup" to begin the process
6. Review logs in the interface and in `aws_cleanup.log`

## Security Considerations

- Always run in "Dry Run" mode first to verify what resources will be affected
- The tool defaults to "Dry Run" mode for safety
- Make sure your AWS profiles have the necessary permissions for the resources you want to clean
- Use this tool with caution as it can permanently delete resources

## AWS Permission Requirements

The AWS user/role should have the following permissions:

- `ec2:*` - For EC2, VPC resource management
- `s3:*` - For S3 bucket and object management
- `lambda:*` - For Lambda function management
- `cloudformation:*` - For CloudFormation stack management
- `rds:*` - For RDS resource management
- `iam:*` - For IAM resource management (be especially careful with this)

## Project Structure

```
aws_cleaner/
├── aws_cleanup_gui.py # Main GUI application
├── cleaner/ # Resource-specific cleaner modules
│   ├── __init__.py
│   ├── ec2.py
│   ├── s3.py
│   ├── lambda_module.py
│   ├── cloudformation.py
│   ├── rds.py
│   ├── vpc.py
│   └── iam.py
└── aws_cleanup.log # Log file (created when app runs)
```

## License

MIT

## Disclaimer

This tool can permanently delete AWS resources. Use at your own risk and always test in dry run mode first. 