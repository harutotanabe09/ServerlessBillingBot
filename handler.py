#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import boto3
import json
import urllib.request as requests
from datetime import datetime, timedelta, date

SLACK_WEBHOOK_URL = os.environ.get('slack_url')

def lambda_handler(event, context) -> None:
    client = boto3.client('ce', region_name='ap-northeast-1')
    # 合計とサービス毎の請求額を取得する
    total_billing = get_total_billing(client)
    service_billings = get_service_billings(client)
    # Slack用のメッセージを作成して投げる
    (title, detail) = get_message(total_billing, service_billings)
    post_slack(title, detail)

def get_total_billing(client) -> dict:
    (start_date, end_date) = get_total_cost_date_range()
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ce.html#CostExplorer.Client.get_cost_and_usage
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ]
    )
    return {
        'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
        'end': response['ResultsByTime'][0]['TimePeriod']['End'],
        'billing': response['ResultsByTime'][0]['Total']['AmortizedCost']['Amount'],
    }


def get_service_billings(client) -> list:
    (start_date, end_date) = get_total_cost_date_range()
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )
    billings = []
    for item in response['ResultsByTime'][0]['Groups']:
        billings.append({
            'service_name': item['Keys'][0],
            'billing': item['Metrics']['AmortizedCost']['Amount']
        })
    return billings


def get_message(total_billing: dict, service_billings: list) -> (str, str):
    start = datetime.strptime(total_billing['start'], '%Y-%m-%d').strftime('%m/%d')
    # Endの日付は結果に含まないため、表示上は前日にしておく
    end_today = datetime.strptime(total_billing['end'], '%Y-%m-%d')
    end_yesterday = (end_today - timedelta(days=1)).strftime('%m/%d')
    total = round(float(total_billing['billing']), 2)
    title = f' :moneybag: {start}～{end_yesterday}の請求額は、{total:.2f} USD やで~。大阪リージョンやで~。 '
    details = []
    for item in service_billings:
        service_name = item['service_name']
        billing = round(float(item['billing']), 2)
        if billing == 0.0:
            # 請求無し（0.0 USD）の場合は、内訳を表示しない
            continue
        details.append(f' :money_with_wings: 　・{service_name}: {billing:.2f} USD')
    return title, '\n'.join(details)

def post_slack(title: str, detail: str) -> None:
    # https://api.slack.com/incoming-webhooks
    # https://api.slack.com/docs/message-formatting
    # https://api.slack.com/docs/messages/builder
    payload = {
        'blocks': [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "大阪の請求Botやで~"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This is a New Slack WebHook <https://api.slack.com/reference/block-kit/blocks#context|this is a link>"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": detail
                },
            },
        ]
    }
    request_headers = { 'Content-Type': 'application/json; charset=utf-8' }
    body = json.dumps(payload).encode("utf-8")
    request = requests.Request(
        url=SLACK_WEBHOOK_URL, 
        data=body,
        method='POST',
        headers=request_headers 
    )
    requests.urlopen(request)

def get_total_cost_date_range() -> (str, str):
    start_date = get_begin_of_month()
    end_date = get_today()
    # get_cost_and_usage()のstartとendに同じ日付は指定不可のため、
    # 「今日が1日」なら、「先月1日から今月1日（今日）」までの範囲にする
    if start_date == end_date:
        end_of_month = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=-1)
        begin_of_month = end_of_month.replace(day=1)
        return begin_of_month.date().isoformat(), end_date
    return start_date, end_date


def get_begin_of_month() -> str:
    return date.today().replace(day=1).isoformat()


def get_prev_day(prev: int) -> str:
    return (date.today() - timedelta(days=prev)).isoformat()


def get_today() -> str:
    return date.today().isoformat()