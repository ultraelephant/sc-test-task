import csv
import imp
import sys
import json
import boto3

from datetime import datetime
from multiprocessing import Process

tervar = imp.load_source("tervar", "./terraform.tfvars")
queuename = '{}-queue'.format(tervar.project_name)

def testfile(filename,s3object,fieldslist):
  
  sqs_client = boto3.client('sqs')
  sqs_queue_url = sqs_client.get_queue_url(QueueName=queuename)['QueueUrl']
  
  
  errormessage = {}
  data = s3object['Body'].read()
  contents = data.decode('utf-8')
  
  with open('/tmp/{}'.format(filename), 'a') as csv_data:
    csv_data.write(contents)
  
  file = open('/tmp/{}'.format(filename), "r")
  dict_reader = csv.DictReader(file)
  for entry in list(dict_reader):
    for field in fieldslist:
      if field not in entry:
        errormessage['type']='error_message'
        errormessage['client_reference']=None
        errormessage['portfolio_reference']=None
        errormessage['message']='{} have no field {}'.format(filename,field)
        msg = sqs_client.send_message(QueueUrl=sqs_queue_url,MessageBody=json.dumps(errormessage))
        sys.exit(0)
  
  return True
  

def processclients(clientscsv,portfolioscsv,transactionscsv):

  sqs_client = boto3.client('sqs')
  sqs_queue_url = sqs_client.get_queue_url(QueueName=queuename)['QueueUrl']
  
  file_cl = open('/tmp/{}'.format(clientscsv), "r")
  dict_reader_cl = csv.DictReader(file_cl)
  file_pf = open('/tmp/{}'.format(portfolioscsv), "r")
  dict_reader_pf = csv.DictReader(file_pf)
  file_tr = open('/tmp/{}'.format(transactionscsv), "r")
  dict_reader_tr = csv.DictReader(file_tr)
  
  for entry_cl in list(dict_reader_cl):
    clientmessage = {}
    clienttax = 0.00
    json_from_csv_cl = entry_cl
    clientmessage['type']='client_message'

    clientmessage['client_reference']=json_from_csv_cl['client_reference']
    clientmessage['tax_free_allowance']=json_from_csv_cl['tax_free_allowance']

    for entry_pf in list(dict_reader_pf):
      json_from_csv_pf = entry_pf

      if json_from_csv_pf['client_reference'] == json_from_csv_cl['client_reference']:
        for entry_tr in list(dict_reader_tr):
          json_from_csv_tr = entry_tr

          if json_from_csv_tr['accout_number'] == json_from_csv_pf['accout_number'] and json_from_csv_tr['keyword'] == 'TAX':

            try:
              clienttax = clienttax + -float(json_from_csv_tr['amount'])
            except:
              clientmessage['type']='error_message'
              clientmessage['portfolio_reference']=json_from_csv_pf['portfolio_reference']
              clientmessage['message']='failed to calculate taxes_paid'
              del (clientmessage['tax_free_allowance'])
              msg = sqs_client.send_message(QueueUrl=sqs_queue_url,MessageBody=json.dumps(clientmessage))
              return 0

        file_tr.seek(0)
    file_pf.seek(0)
    clientmessage['taxes_paid'] = clienttax

    msg = sqs_client.send_message(QueueUrl=sqs_queue_url,MessageBody=json.dumps(clientmessage))


def processportfolios(portfolioscsv,accountscsv,transactionscsv):

  sqs_client = boto3.client('sqs')
  sqs_queue_url = sqs_client.get_queue_url(QueueName=queuename)['QueueUrl']

  file_pf = open('/tmp/{}'.format(portfolioscsv), "r")
  dict_reader_pf = csv.DictReader(file_pf)
  file_ac = open('/tmp/{}'.format(accountscsv), "r")
  dict_reader_ac = csv.DictReader(file_ac)
  file_tr = open('/tmp/{}'.format(transactionscsv), "r")
  dict_reader_tr = csv.DictReader(file_tr)
  
  for entry_pf in list(dict_reader_pf):
    trqty = 0
    dep = 0
    portfoliomessge = {}
    json_from_csv_pf = entry_pf
    portfoliomessge['type']='portfolio_message'
    portfoliomessge['portfolio_reference']=json_from_csv_pf['portfolio_reference']

    for entry_ac in list(dict_reader_ac):
      json_from_csv_ac = entry_ac
      portfoliomessge['cash_balance']=json_from_csv_ac['cash_balance']
    file_ac.seek(0)

    for entry_tr in list(dict_reader_tr):
      json_from_csv_tr = entry_tr

      if json_from_csv_tr['accout_number'] == json_from_csv_pf['accout_number']:
        trqty = trqty + 1
        if json_from_csv_tr['keyword'] == 'DEPOSIT':
          try:
            dep = dep + float(json_from_csv_tr['amount'])
          except:
            portfoliomessge['type']='error_message'
            portfoliomessge['client_reference']=None
            portfoliomessge['message']='failed to calculate deposites'
            del (portfoliomessge['cash_balance'])
            msg = sqs_client.send_message(QueueUrl=sqs_queue_url,MessageBody=json.dumps(portfoliomessge))
            return 0

      file_tr.seek(0)
    portfoliomessge['number_of_transactions'] = trqty
    portfoliomessge['sum_of_deposits'] = dep 
    msg = sqs_client.send_message(QueueUrl=sqs_queue_url,MessageBody=json.dumps(portfoliomessge))

def processed_files(bucket_name,filename):
  s3 = boto3.resource('s3')
  s3.Object(bucket_name, 'processed/{}-processed'.format(filename)).copy_from(CopySource='{}/{}'.format(bucket_name,filename))
  s3.Object(bucket_name, filename).delete()

def lambda_handler(event, context):
  s3 = boto3.client('s3')
  lambda_client = boto3.client('lambda')
  
  todaytimestamp = datetime.now()
  datetimemask = "%Y%m%d"
  bucket_name = event['Records'][0]['s3']['bucket']['name']
  clientscsv = 'clients_{}.csv'.format(todaytimestamp.strftime(datetimemask))
  accountscsv = 'accounts_{}.csv'.format(todaytimestamp.strftime(datetimemask))
  portfolioscsv = 'portfolios_{}.csv'.format(todaytimestamp.strftime(datetimemask))
  transactionscsv = 'transactions_{}.csv'.format(todaytimestamp.strftime(datetimemask))
  
  clientsfields = ['record_id','first_name','last_name','client_reference','tax_free_allowance']
  accountsfields = ['record_id','accout_number','cash_balance','currency','taxes_paid']
  portfoliosfields = ['record_id','accout_number','portfolio_reference','client_reference','agent_code']
  transactionsfields = ['record_id','accout_number','transaction_reference','amount','keyword']
  
  find = 0
  
  for file in s3.list_objects(Bucket=bucket_name)['Contents']:
    if file['Key'] == clientscsv or file['Key'] == accountscsv or file['Key'] == portfolioscsv or file['Key'] == transactionscsv:
      find = find +1
      if find == 4:
        csv_object_cl = s3.get_object(Bucket=bucket_name, Key=clientscsv)
        csv_object_ac = s3.get_object(Bucket=bucket_name, Key=accountscsv)
        csv_object_pf = s3.get_object(Bucket=bucket_name, Key=portfolioscsv)
        csv_object_tr = s3.get_object(Bucket=bucket_name, Key=transactionscsv)
        if testfile(clientscsv,csv_object_cl,clientsfields) and testfile(accountscsv,csv_object_ac,accountsfields) and testfile(portfolioscsv,csv_object_pf,portfoliosfields) and testfile(transactionscsv,csv_object_tr,transactionsfields):
          p1 = Process(target=processclients(clientscsv,portfolioscsv,transactionscsv))
          p1.start()
          p2 = Process(target=processportfolios(portfolioscsv,accountscsv,transactionscsv))
          p2.start()
          p1.join()
          p2.join()
          processed_files(bucket_name,clientscsv)
          processed_files(bucket_name,accountscsv)
          processed_files(bucket_name,portfolioscsv)
          processed_files(bucket_name,transactionscsv)
          return 0

  print ('Files not ready')