# Use the official AWS Lambda Python 3.9 base image
FROM public.ecr.aws/lambda/python:3.9

# 1. Install system dependencies if needed (psycopg binary usually doesn't need these, but good for safety)
# RUN yum install -y gcc python3-devel

# 2. Copy requirements.txt from the root of the project
# Note: The 'context' in your YAML is '.', so we pull from the root
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# 3. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the application source code and lambda handlers
# We copy them into the task root so they are importable
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY deployment/lambda/ ${LAMBDA_TASK_ROOT}/deployment/lambda/

# 5. Set the CMD to your daily run handler
# Format: [folder_path].[file_name].[function_name]
# Adjust 'handler' if your function name in lambda_daily_run.py is different
CMD [ "deployment.lambda.lambda_daily_run.lambda_handler" ]