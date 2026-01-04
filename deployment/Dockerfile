FROM public.ecr.aws/lambda/python:3.9

# Copy requirements first to leverage Docker cache
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY deployment/lambda/ ${LAMBDA_TASK_ROOT}/deployment/lambda/

# Ensure the path is set so imports work
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${LAMBDA_TASK_ROOT}/src"

CMD [ "deployment.lambda.lambda_daily_run.lambda_handler" ]