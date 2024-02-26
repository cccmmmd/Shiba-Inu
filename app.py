import sys
import configparser

# Azure CLU
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient

from flask import Flask, request, abort, render_template
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage
)

#Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

#Azure CLU Key
clu_endpoint = config['AzureCLU']['END_POINT']
clu_key = config['AzureCLU']['KEY']
project_name = config['AzureCLU']['PROJECT_NAME']
deployment_name = config['AzureCLU']['DEPLOYMENT_NAME']

app = Flask(__name__)

channel_access_token = config['Line']['CHANNEL_ACCESS_TOKEN']
channel_secret = config['Line']['CHANNEL_SECRET']
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)

configuration = Configuration(
    access_token=channel_access_token
)
dog_img_url = ''
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):
    global dog_img_url 
    # analyze quey
    result = azure_clu(event.message.text)
    # print(result)

    intent = result['result']['prediction']['topIntent']
    returnMessages = []
    # returnMessages.append(TextMessage(text=f"意圖判斷：{intent}"))
    url = config['Deploy']['URL']+'/static/img/'

    def bark():
        return 'bark.gif'
    def scratch():
        return 'scratch.gif'
    def tail():
        return 'tail.gif'
    def head():
        return 'head.gif'
    def hand():
        return 'hand.gif'
    def call():
        return 'call.gif'
    def catch():
        return 'catch.gif'


    dog_movement = {
        'Bark': bark,
        'Scratch': scratch,
        'Wag tail': tail,
        'Head': head,
        'Shake hand': hand,
        'Call': call,
        'Catch ball': catch
    }

    def dog_response(command):
        imgurl = dog_movement.get(command, lambda: '柴柴不知道你說的是什麼')()
        return imgurl
    
    if len(result['result']['prediction']['entities']) > 0:
        dog_img_url = dog_response(intent)
        temp_url = url + dog_response(intent)
        returnMessages.append(
            ImageMessage(original_content_url=temp_url, preview_image_url=temp_url))
    else:
        returnMessages.append(TextMessage(text="柴柴我不知道你說什麼"))
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=returnMessages
            )
        )
@app.route("/")
def home():
    return render_template('index.html')
@app.route("/imgurl")
def products():
    return {"imgurl": dog_img_url }, 200
def azure_clu(user_input):
    client = ConversationAnalysisClient(clu_endpoint, AzureKeyCredential(clu_key))
    with client:
        query = user_input
        result = client.analyze_conversation(
            task={
                "kind": "Conversation",
                "analysisInput": {
                    "conversationItem": {
                        "participantId": "1",
                        "id": "1",
                        "modality": "text",
                        "language": "zh-hant",
                        "text": query
                    },
                    "isLoggingEnabled": False
                },
                "parameters": {
                    "projectName": project_name,
                    "deploymentName": deployment_name,
                    "verbose": True
                }
            }
        )
        return result
if __name__ == "__main__":
    app.run()