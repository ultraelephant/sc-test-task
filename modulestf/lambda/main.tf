module "lambda_archive" {
  source = "./archive"
}


module "iam" {
  source = "./iam"

  project_name = "${var.project_name}"
  s3_arn = "${var.s3_arn}"
  sqs_arn = "${var.sqs_arn}"
}


resource "aws_lambda_function" "lambda" {
  filename = "${module.lambda_archive.path}"
  function_name = "${var.project_name}-lambda"
  handler = "lambda_function.lambda_handler"
  source_code_hash = "${module.lambda_archive.payload}"
  runtime = "python3.8"
  memory_size = "128"
  timeout = "10"
  reserved_concurrent_executions = "1"
  role = "${module.iam.arn}"

  tags = {
    Name   = "${var.project_name}-bucket"
  }

  environment {
    variables = {
      queue_name = "${var.sqs_name}"
    }
  }
}

resource "aws_lambda_permission" "allow_bucket" {
  statement_id = "AllowExecutionFromS3Bucket"
  action = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.lambda.arn}"
  principal = "s3.amazonaws.com"
  source_arn = "${var.s3_arn}"
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = "${var.s3_id}"

  lambda_function {
    lambda_function_arn = "${aws_lambda_function.lambda.arn}"
    events = ["s3:ObjectCreated:*"]
    filter_suffix = ".csv"
  }
}