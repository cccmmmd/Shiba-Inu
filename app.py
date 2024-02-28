import sys
import configparser

# Azure Speech
import os
import azure.cognitiveservices.speech as speechsdk
import librosa

# Azure CLU
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient

# Gemini
import pathlib
import textwrap
import google.generativeai as genai

from IPython.display import display
from IPython.display import Markdown


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
    ImageMessage,
    AudioMessage
)

#Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

# Azure Speech Settings
speech_config = speechsdk.SpeechConfig(subscription=config['AzureSpeech']['SPEECH_KEY'], 
                                       region=config['AzureSpeech']['SPEECH_REGION'])
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
UPLOAD_FOLDER = 'static'

#Azure CLU Key
clu_endpoint = config['AzureCLU']['END_POINT']
clu_key = config['AzureCLU']['KEY']
project_name = config['AzureCLU']['PROJECT_NAME']
deployment_name = config['AzureCLU']['DEPLOYMENT_NAME']

# Gemini
genai.configure(api_key=config['Gemini']['GOOGLE_API_KEY'])
model = genai.GenerativeModel('gemini-pro')

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
file_name = ''

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
    global dog_img_url, file_name
    # analyze quey
    result = azure_clu(event.message.text)
    g_response = ''
    # print(result)

    intent = result['result']['prediction']['topIntent']
    returnMessages = []
    # returnMessages.append(TextMessage(text=f"意圖判斷：{intent}"))
    url = config['Deploy']['URL']+'/static/img/'

    def bark():
        return ['bark.gif','假裝你是小狗，在汪汪叫後，說出一句話']
    def scratch():
        return ['scratch.gif','假裝你是小狗，正在搔癢並說出一句話']
    def tail():
        return ['tail.gif','假裝你是小狗，很開心的搖尾巴並說出一句話']
    def head():
        return ['head.gif','假裝你是小狗，主人正在摸你的頭，你很開心並說出一句話']
    def hand():
        return ['hand.gif','假裝你是小狗，正在和主人握手並說出一句話']
    def call():
        return ['call.gif','假裝你是小狗，在主人叫你名字後，興奮的說一句回應的話']
    def catch():
        return ['catch.gif','假裝你是小狗，在接住球後說出一句高興的話']


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
        dog_img_url = dog_response(intent)[0]
        file_name = dog_response(intent)[0] + ".wav"
    
        g_response = model.generate_content([dog_response(intent)[1]])
        returnMessages.append(
            ImageMessage(original_content_url=url + dog_response(intent)[0], preview_image_url=url + dog_response(intent)[0]))
    else:
        returnMessages.append(TextMessage(text="柴柴我不知道你說什麼"))
    
    if len(result['result']['prediction']['entities']) > 0:
        azure_speech(g_response.text)

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
    test = os.listdir('static/')
    for item in test:
        if item.endswith(".wav"):
            os.remove(os.path.join('static/', item))

    return render_template('index.html')
@app.route("/imgurl")
def products():
    return {"imgurl": dog_img_url, "audio": file_name}, 200
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

def azure_speech(user_input):
    global file_name
    # The language of the voice that speaks.
    # if(user_input)
    speech_config.speech_synthesis_voice_name='zh-TW-YunJheNeural'
    file_config = speechsdk.audio.AudioOutputConfig(filename='static/'+file_name)
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=file_config)

    # Receives a text from console input and synthesizes it to wave file.
    result = speech_synthesizer.speak_text_async(user_input).get()
    # Check result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized for text [{}], and the audio was saved to [{}]".format(user_input, file_name))
        audio_duration = round(librosa.get_duration(path=f'static/{file_name}')*1000)
        # print(audio_duration)
        return audio_duration
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        # print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))

if __name__ == "__main__":
    app.run()