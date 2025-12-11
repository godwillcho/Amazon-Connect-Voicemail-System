#!/bin/bash

# CloudFormation Deployment Script for Amazon Connect Voicemail System
# Usage: ./deploy-cfn.sh [stack-name] [region]

set -e

STACK_NAME=${1:-voicemail-system}
REGION=${2:-us-west-2}
TEMPLATE_FILE="cloudformation/voicemail-stack.yaml"
PARAMS_FILE="cloudformation/parameters.json"

echo "========================================="
echo "CloudFormation Deployment"
echo "Amazon Connect Voicemail System"
echo "========================================="
echo ""
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Check if template exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "❌ Template file not found: $TEMPLATE_FILE"
    exit 1
fi

# Check if parameters file exists
if [ ! -f "$PARAMS_FILE" ]; then
    echo "⚠️  Parameters file not found: $PARAMS_FILE"
    echo ""
    echo "Creating from example..."
    
    if [ ! -f "cloudformation/parameters.json.example" ]; then
        echo "❌ Example parameters file not found"
        exit 1
    fi
    
    cp cloudformation/parameters.json.example cloudformation/parameters.json
    
    echo ""
    echo "📝 Please edit cloudformation/parameters.json with your values:"
    echo "   - EmailSender (required)"
    echo "   - ConnectInstanceId (required)"
    echo "   - ConnectInstanceArn (required)"
    echo ""
    read -p "Press Enter after editing parameters file..."
fi

# Validate template
echo "🔍 Validating template..."
aws cloudformation validate-template \
    --template-body file://$TEMPLATE_FILE \
    --region $REGION &> /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Template is valid"
else
    echo "❌ Template validation failed"
    exit 1
fi

# Check if stack exists
echo ""
echo "🔍 Checking if stack exists..."

if aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION &> /dev/null; then
    
    echo "Stack exists. Updating..."
    OPERATION="update"
    
    aws cloudformation update-stack \
        --stack-name $STACK_NAME \
        --template-body file://$TEMPLATE_FILE \
        --parameters file://$PARAMS_FILE \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
    
    if [ $? -eq 0 ]; then
        echo "✅ Stack update initiated"
        
        echo ""
        echo "⏳ Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name $STACK_NAME \
            --region $REGION
        
        echo "✅ Stack updated successfully"
    else
        # Check if no changes needed
        if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
            echo "ℹ️  No changes needed"
        else
            echo "❌ Stack update failed"
            exit 1
        fi
    fi
else
    echo "Stack does not exist. Creating..."
    OPERATION="create"
    
    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://$TEMPLATE_FILE \
        --parameters file://$PARAMS_FILE \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
    
    if [ $? -eq 0 ]; then
        echo "✅ Stack creation initiated"
        
        echo ""
        echo "⏳ Waiting for stack creation to complete (this may take 3-5 minutes)..."
        aws cloudformation wait stack-create-complete \
            --stack-name $STACK_NAME \
            --region $REGION
        
        echo "✅ Stack created successfully"
    else
        echo "❌ Stack creation failed"
        exit 1
    fi
fi

# Get stack outputs
echo ""
echo "========================================="
echo "Stack Outputs"
echo "========================================="

aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Get important values
echo ""
echo "========================================="
echo "Important Information"
echo "========================================="

LAMBDA_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text 2>/dev/null)

S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
    --output text 2>/dev/null)

if [ ! -z "$LAMBDA_NAME" ]; then
    echo "Lambda Function: $LAMBDA_NAME"
fi

if [ ! -z "$S3_BUCKET" ]; then
    echo "S3 Bucket: $S3_BUCKET"
fi

echo ""
echo "========================================="
echo "Next Steps"
echo "========================================="
echo ""
echo "1. Deploy Lambda code:"
echo "   cd lambda"
echo "   zip function.zip lambda_function.py"
echo "   aws lambda update-function-code \\"
echo "     --function-name $LAMBDA_NAME \\"
echo "     --zip-file fileb://function.zip \\"
echo "     --region $REGION"
echo ""
echo "2. Verify SES sender email:"
echo "   aws ses verify-email-identity \\"
echo "     --email-address YOUR_EMAIL \\"
echo "     --region $REGION"
echo ""
echo "3. Configure Amazon Connect:"
echo "   - Go to Connect Console → Data storage"
echo "   - Set S3 bucket: $S3_BUCKET"
echo "   - Set prefix: connect/recordings"
echo ""
echo "4. Import Connect flow:"
echo "   - Upload connect-flow/VoiceMailModule.json"
echo "   - Update Lambda ARN in flow"
echo "   - Publish flow"
echo ""
echo "5. Test the system!"
echo ""
echo "========================================="
echo "✅ Deployment complete!"
echo "========================================="
