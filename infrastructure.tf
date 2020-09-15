provider "aws" {
	access_key = "${var.access_key}"
	secret_key = "${var.secret_key}"
	region = "${var.region}"
}

#####s3 bucket BEGIN#####

resource "aws_s3_bucket" "csv" {
  bucket = "${var.project_name}-bucket"
  acl    = "private"

  tags = {
    Name   = "${var.project_name}-bucket"
  }
}

#####s3 bucket END#####


#####sqs BEGIN#####

resource "aws_sqs_queue" "queue" {
  name = "${var.project_name}-queue"

  tags = {
    Name   = "${var.project_name}-bucket"
  }
}

#####sqs END#####


#####lambda BEGIN#####

locals {
  source_files = ["./lambda_function.py", "./terraform.tfvars"]
}

data "template_file" "t_file" {
  count = "${length(local.source_files)}"
  template = "${file(element(local.source_files, count.index))}"
}

resource "local_file" "to_temp_dir" {
  count    = "${length(local.source_files)}"
  filename = "${path.module}/temp/${basename(element(local.source_files, count.index))}"
  content  = "${element(data.template_file.t_file.*.rendered, count.index)}"
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "lambda.zip"
  source_dir = "${path.module}/temp"

  depends_on = [
    "local_file.to_temp_dir",
  ]
}

data "aws_iam_policy_document" "lambda" {
  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = ["${aws_s3_bucket.csv.arn}"]
  }
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.csv.arn}/*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "sqs:GetQueueUrl",
      "sqs:SendMessage",
    ]
    resources = ["${aws_sqs_queue.queue.arn}"]
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  policy = "${data.aws_iam_policy_document.lambda.json}"
}

resource "aws_iam_role" "lambda_role" {
  name = "LambdaRole-${var.project_name}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "lambda" {
  role = "${aws_iam_role.lambda_role.name}"
  policy_arn = "${aws_iam_policy.lambda_policy.arn}"
}

resource "aws_lambda_function" "lambda" {
  filename = "${data.archive_file.lambda_zip.output_path}"
  function_name = "${var.project_name}-lambda"
  handler = "lambda_function.lambda_handler"
  source_code_hash = "${data.archive_file.lambda_zip.output_base64sha256}"
  runtime = "python3.8"
  memory_size = "128"
  timeout = "10"
  reserved_concurrent_executions = "1"
  role = "${aws_iam_role.lambda_role.arn}"

  tags = {
    Name   = "${var.project_name}-bucket"
  }
}

resource "aws_lambda_permission" "allow_bucket" {
  statement_id = "AllowExecutionFromS3Bucket"
  action = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.lambda.arn}"
  principal = "s3.amazonaws.com"
  source_arn = "${aws_s3_bucket.csv.arn}"
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = "${aws_s3_bucket.csv.id}"

  lambda_function {
    lambda_function_arn = "${aws_lambda_function.lambda.arn}"
    events = ["s3:ObjectCreated:*"]
    filter_suffix = ".csv"
  }
}

#####lambda END#####