#!/bin/bash

# Amazon Connect Voicemail System - Deployment Script
# Usage: ./deploy.sh [function-name] [region]

set -e

# Configuration
FUNCTION_NAME=${1:-voicemail-transcribe-email}
REGION=${2:-us-west-2}
LAMBDA_DIR="lambda"
ZIP_FILE="function.zip"

echo "========================================="
echo "Amazon Connect Voicemail System"
echo "Deployment Script"
echo "========================================="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

echo "✅ AWS CLI found"

# Check for Lambda function file
if [ ! -f "$LAMBDA_DIR/lambda_function.py" ]; then
    echo "❌ Lambda function not found at $LAMBDA_DIR/lambda_function.py"
    exit 1
fi

echo "✅ Lambda function found"

# Create deployment package
echo ""
echo "📦 Creating deployment package..."
cd $LAMBDA_DIR
zip -q $ZIP_FILE lambda_function.py
cd ..

if [ ! -f "$LAMBDA_DIR/$ZIP_FILE" ]; then
    echo "❌ Failed to create deployment package"
    exit 1
fi

echo "✅ Deployment package created"

# Check if function exists
echo ""
echo "🔍 Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    echo "✅ Function exists - updating code..."
    
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$LAMBDA_DIR/$ZIP_FILE \
        --region $REGION \
        --output text &> /dev/null
    
    echo "✅ Function code updated"
else
    echo "❌ Function does not exist. Please create it first using:"
    echo ""
    echo "aws lambda create-function \\"
    echo "  --function-name $FUNCTION_NAME \\"
    echo "  --runtime python3.9 \\"
    echo "  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \\"
    echo "  --handler lambda_function.lambda_handler \\"
    echo "  --zip-file fileb://$LAMBDA_DIR/$ZIP_FILE \\"
    echo "  --timeout 180 \\"
    echo "  --memory-size 512 \\"
    echo "  --region $REGION"
    exit 1
fi

# Cleanup
rm $LAMBDA_DIR/$ZIP_FILE

echo ""
echo "========================================="
echo "✅ Deployment completed successfully!"
echo "========================================="
echo ""
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""
echo "Next steps:"
echo "1. Configure environment variables in AWS Console"
echo "2. Import Connect flow from connect-flow/VoiceMailModule.json"
echo "3. Update Lambda ARN in Connect flow"
echo "4. Test the voicemail system"
echo ""
