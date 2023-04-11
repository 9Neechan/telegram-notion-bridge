import requests
import base64
import json
import os
import re
import api_config

from datetime import datetime

from telethon import TelegramClient, sync, events
from telethon import functions, types
from telethon.extensions import markdown

client = TelegramClient('session_name', api_config.api_id, api_config.api_hash)

base_url = 'https://api.notion.com/v1/pages'


def readDatabase(databaseId, headers):
    readUrl = f"https://api.notion.com/v1/databases/{databaseId}/query"

    res = requests.request("POST", readUrl, headers=headers)
    data = res.json()
    print(res.status_code)
    # print(res.text)

    with open('./db.json', 'w', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False)


def createPage(title, notion_db_id):
    page = {
        "parent": {"database_id": f"{notion_db_id}"},
        "properties": {
            "title": {
                "title": [
                    {
                        "text": {
                            "content": title[:90]
                        }
                    }
                ]
            }
        },
        "children": []
    }
    return page


def createDate():
    iso_date = datetime.now().isoformat('T')

    return {
        "date": {
            "start": iso_date
        }
    }


def createParagraph(array_rich_text=[]):
    paragraph = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": array_rich_text
        }
    }
    return paragraph


def createRichText(text, url=''):
    text = {
        "type": "text",
        "text": {
            "content": text
        }
    }
    if url:
        text['text']['link'] = {
            "type": "url",
            "url": url
        }

    return text


def skipFirstParagraph(text):
    if len(text.split()) > 1:
        return '\n'.join(text.split('\n')[1:])
    else:
        return ''


def parse_paragraph(text):
    res = []

    url_search = re.search(r'\[[\w\s\d\-\./:_@\"?=&;]+\]\([\w\s\d\-\./:_@\"?=&;]+\)', text)
    url_search_link = re.search(r'https?://[\w\s\d\-\./:_@\"?=&;]+', text)

    if url_search:
        url_search = url_search.group(0)
        ind_separator = url_search.find('|')

        start_index = text.find(url_search)
        end_index = start_index + len(url_search)

        start = parse_paragraph(text[:start_index])
        end = parse_paragraph(text[end_index:])

        for i in range(len(start)):
            res.append(start[i])

        sep_index = url_search.find('](')
        res.append(createRichText(url_search[1:sep_index], url_search[sep_index + 2:-1]))

        for i in range(len(end)):
            res.append(end[i])

    elif url_search_link:
        url_search_link = url_search_link.group(0)

        start_index = text.find(url_search_link)
        end_index = start_index + len(url_search_link)

        start = parse_paragraph(text[:start_index])
        end = parse_paragraph(text[end_index:])

        for i in range(len(start)):
            res.append(start[i])

        res.append(createRichText(url_search_link, url_search_link))

        for i in range(len(end)):
            res.append(end[i])
    else:
        res.append(createRichText(text))

    return res


def createParagraphsWithUrl(event):
    if event.entities == None:
        return []

    msg_text = event.message.message
    msg_text = markdown.unparse(msg_text, event.entities)

    print("msg:\n", msg_text[:30])

    paragraphs = []

    while msg_text[0] == '#' or 'REPOST' in msg_text.split('\n')[0] or msg_text.split('\n')[0] == '':
        msg_text = skipFirstParagraph(msg_text)

    print("len:\n", msg_text)

    for paragraph in msg_text.split('\n'):
        rech_text_row = parse_paragraph(paragraph)
        paragraphs.append(createParagraph(rech_text_row))

    return paragraphs


def createImg(url):
    img = {
        "type": "image",
        "image": {
            "type": "external",
            "external": {
                "url": url
            }
        }
    }
    return img


def removeFile(file):
    if os.path.isfile(file):
        os.remove(file)
    else:  ## Show an error ##
        print("Error: %s file not found" % file)


@client.on(events.NewMessage(chats=api_config.tg_chat))  # !!!!!!!!!!
async def newPostInChannel(event):
    # print(event)
    # определяем, какой по индексу канал отправил запрос
    i = -1
    channel_id = event.peer_id.channel_id
    i = api_config.channels_id.index(channel_id)

    msg_text = event.message.message

    img_url = ''
    if event.message.photo:
        path = await event.message.download_media(thumb=-1)
        # print(path)
        with open(path, "rb") as file:
            url = "https://api.imgbb.com/1/upload"
            payload = {
                "key": api_config.key_imgbb,
                "image": base64.b64encode(file.read()),
            }
            res = requests.post(url, payload).json()
            img_url = res['data']['url']

        removeFile(path)

    if len(msg_text):
        if msg_text[0] == '#':
            msg_text = '\n'.join(msg_text.split('\n')[1:])

        page = createPage(msg_text.split('\n')[0], api_config.notion_database_id[i])  # !!!!!!!!!

        paragraphs = createParagraphsWithUrl(event)
        page['children'] = paragraphs

        if img_url:
            page['children'].append(createImg(img_url))
        else:
            page['children'].append(createImg(api_config.imgbb_img_url))  # !!!!!!!!!!!

        page['properties']['Date'] = createDate()

        headers = {
            'Authorization': f'Bearer {api_config.notion_key[i]}',  # !!!!!!!!!!!!!
            'Content-Type': 'application/json',
            'Notion-Version': '2022-06-28'
        }

        response = requests.post(base_url, headers=headers, json=page)
        print(response.json())


client.start()
client.run_until_disconnected()
