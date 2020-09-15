#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import csv
import imp
import sys
import json
import boto3

from datetime import datetime
from multiprocessing import Process

queue_name = os.environ['queue_name']


def csv_data_model_compliant_check(file_name, s3_object, fields_list):

    sqs_client = boto3.client('sqs')
    sqs_queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
    error_message = {}
    data = s3_object['Body'].read()
    contents = data.decode('utf-8')

    with open('/tmp/{}'.format(file_name), 'a') as csv_data:
        csv_data.write(contents)

    with open('/tmp/{}'.format(file_name), 'r') as file:
        csv_reader = csv.DictReader(file)
        dict_reader = list(csv_reader)

    for entry in dict_reader:
        for field in fields_list:
            if field not in entry:
                error_message['type'] = 'error_message'
                error_message['client_reference'] = None
                error_message['portfolio_reference'] = None
                error_message['message'] = '{} have no field {}'.format(file_name, field)
                msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(error_message))
                return False

    return True


def process_clients(clients_csv, portfolios_csv, transactions_csv):

    sqs_client = boto3.client('sqs')
    sqs_queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']

    with open('/tmp/{}'.format(clients_csv), 'r') as file_clients:
        csv_reader_clients = csv.DictReader(file_clients)
        dict_reader_clients = list(csv_reader_clients)
    with open('/tmp/{}'.format(portfolios_csv), 'r') as file_portfolios:
        csv_reader_portfolios = csv.DictReader(file_portfolios)
        dict_reader_portfolios = list(csv_reader_portfolios)
    with open('/tmp/{}'.format(transactions_csv), 'r') as file_transactions:
        csv_reader_transactions = csv.DictReader(file_transactions)
        dict_reader_transactions = list(csv_reader_transactions)

    for entry_clients in dict_reader_clients:
        error_skip = False
        client_message = {}
        client_tax = 0.00
        client_message['type'] = 'client_message'
        client_message['client_reference'] = entry_clients['client_reference']
        client_message['tax_free_allowance'] = entry_clients['tax_free_allowance']

        for entry_portfolios in dict_reader_portfolios:
            if entry_portfolios['client_reference'] == entry_clients['client_reference']:
                for entry_transactions in dict_reader_transactions:
                    if entry_transactions['accout_number'] == entry_portfolios['accout_number'] and entry_transactions['keyword'] == 'TAX':

                        try:
                            client_tax = client_tax - float(entry_transactions['amount'])
                        except:
                            client_message['type'] = 'error_message'
                            client_message['portfolio_reference'] = entry_portfolios['portfolio_reference']
                            client_message['message'] = 'failed to calculate taxes_paid'
                            del client_message['tax_free_allowance']
                            msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(client_message))
                            error_skip = True
                            break
            if error_skip:
                break
        if error_skip:
            continue

        client_message['taxes_paid'] = client_tax

        msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(client_message))


def process_portfolios(portfolios_csv, accounts_csv, transactions_csv):

    sqs_client = boto3.client('sqs')
    sqs_queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']

    with open('/tmp/{}'.format(portfolios_csv), 'r') as file_portfolios:
        csv_reader_portfolios = csv.DictReader(file_portfolios)
        dict_reader_portfolios = list(csv_reader_portfolios)
    with open('/tmp/{}'.format(accounts_csv), 'r') as file_accounts:
        csv_reader_accounts = csv.DictReader(file_accounts)
        dict_reader_accounts = list(csv_reader_accounts)
    with open('/tmp/{}'.format(transactions_csv), 'r') as file_transactions:
        csv_reader_transactions = csv.DictReader(file_transactions)
        dict_reader_transactions = list(csv_reader_transactions)

    for entry_portfolios in dict_reader_portfolios:
        error_skip = False
        transactions_quantity = 0
        deposit = 0
        portfolio_message = {}
        portfolio_message['type'] = 'portfolio_message'
        portfolio_message['portfolio_reference'] = entry_portfolios['portfolio_reference']

        for entry_accounts in dict_reader_accounts:
            portfolio_message['cash_balance'] = entry_accounts['cash_balance']

        for entry_transactions in dict_reader_transactions:

            if entry_transactions['accout_number'] == entry_portfolios['accout_number']:
                transactions_quantity = transactions_quantity + 1
                if entry_transactions['keyword'] == 'DEPOSIT':
                    try:
                        deposit = deposit + float(entry_transactions['amount'])
                    except:
                        portfolio_message['type'] = 'error_message'
                        portfolio_message['client_reference'] = None
                        portfolio_message['message'] = 'failed to calculate deposites'
                        del portfolio_message['cash_balance']
                        msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(portfolio_message))
                        error_skip = True
                        break
        if error_skip:
            continue
        portfolio_message['number_of_transactions'] = transactions_quantity
        portfolio_message['sum_of_deposits'] = deposit
        msg = sqs_client.send_message(QueueUrl=sqs_queue_url, MessageBody=json.dumps(portfolio_message))


def move_processed_files(bucket_name, file_name):
    s3 = boto3.resource('s3')
    s3.Object(bucket_name, 'processed/{}-processed'.format(file_name)).copy_from(CopySource='{}/{}'.format(bucket_name, file_name))
    s3.Object(bucket_name, file_name).delete()


def lambda_handler(event, context):
    s3 = boto3.client('s3')
    today_timestamp = datetime.now()
    datetime_mask = '%Y%m%d'
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    clients_csv = 'clients_{}.csv'.format(today_timestamp.strftime(datetime_mask))
    accounts_csv = 'accounts_{}.csv'.format(today_timestamp.strftime(datetime_mask))
    portfolios_csv = 'portfolios_{}.csv'.format(today_timestamp.strftime(datetime_mask))
    transactions_csv = 'transactions_{}.csv'.format(today_timestamp.strftime(datetime_mask))
    clients_fields = ['record_id', 'first_name', 'last_name', 'client_reference', 'tax_free_allowance']
    accounts_fields = ['record_id', 'accout_number', 'cash_balance', 'currency', 'taxes_paid']
    portfolios_fields = ['record_id', 'accout_number', 'portfolio_reference', 'client_reference', 'agent_code']
    transactions_fields = ['record_id', 'accout_number', 'transaction_reference', 'amount', 'keyword']
    find_files = 0

    for file in s3.list_objects(Bucket=bucket_name)['Contents']:
        if file['Key'] == clients_csv or file['Key'] == accounts_csv or file['Key'] == portfolios_csv or file['Key'] == transactions_csv:
            find_files = find_files + 1
            if find_files == 4:
                csv_object_clients = s3.get_object(Bucket=bucket_name, Key=clients_csv)
                csv_object_accounts = s3.get_object(Bucket=bucket_name, Key=accounts_csv)
                csv_object_portfolios = s3.get_object(Bucket=bucket_name, Key=portfolios_csv)
                csv_object_transactions = s3.get_object(Bucket=bucket_name, Key=transactions_csv)
                if (csv_data_model_compliant_check(clients_csv,
                    csv_object_clients, clients_fields),
                    csv_data_model_compliant_check(accounts_csv,
                    csv_object_accounts, accounts_fields),
                    csv_data_model_compliant_check(portfolios_csv,
                    csv_object_portfolios, portfolios_fields),
                    csv_data_model_compliant_check(transactions_csv,
                    csv_object_transactions, transactions_fields)) \
                        == (True, True, True, True):

                    p1 = Process(target=process_clients(clients_csv, portfolios_csv, transactions_csv))
                    p1.start()
                    p2 = Process(target=process_portfolios(portfolios_csv, accounts_csv, transactions_csv))
                    p2.start()
                    p1.join()
                    p2.join()
                    move_processed_files(bucket_name, clients_csv)
                    move_processed_files(bucket_name, accounts_csv)
                    move_processed_files(bucket_name, portfolios_csv)
                    move_processed_files(bucket_name, transactions_csv)
                    return 0
