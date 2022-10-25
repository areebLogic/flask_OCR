import datetime
import io
from PIL import Image
from flask import Flask, request
from pdf2image import convert_from_path
import psycopg2
import requests
import pytesseract
import os
import re
import json


def calculate_total(img):
    text = pytesseract.image_to_string(Image.open(img))
    text = text.split('\n')
    text = [data.lower() for data in text]
    totalCountList = []
    maxTotalList = []
    for i in text:
        if 'total' in i or 't0tal' in i or 'balance' in i or 'subtotal' in i:
            totalCountList.append(i)
    if len(totalCountList) == 0:
        return -1
    else:
        for i in totalCountList:
            if (i.count(',') > 1):
                continue
            else:
                i = i.replace(',', '.')
            maxTotalList.append(re.findall(r"[-+]?\d*\.*\d+", i))
        if max(maxTotalList) == []:
            return -1
        return max(maxTotalList)


conn = psycopg2.connect(
    host="localhost",
    database="ocr",
    user='postgres',
    password='root')
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS ocr_content (id serial PRIMARY KEY,'
            'file_name varchar (150) NOT NULL,'
            'file varchar (150) NOT NULL,'
            'output_text varchar NOT NULL,'
            'date_added date DEFAULT CURRENT_TIMESTAMP);'
            )
conn.commit()
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app = Flask(__name__)
try:
    path = os.path.dirname(os.path.abspath(__file__))
    upload_folder = os.path.join(
        path.replace("/file_folder", ""), "files")
    os.makedirs(upload_folder, exist_ok=True)
    app.config['upload_folder'] = upload_folder
except Exception as e:
    app.logger.info('An error occurred while creating temp folder')
    app.logger.error("Exception occurred : {}".format(e))
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
APP_ROOT = os.path.dirname(os.path.abspath(__file__))


@app.route('/', methods=['POST'])
def scan_file():
    if request.method == 'POST':
        if request.files['file'].content_type == 'application/pdf':
            try:
                pdf_file = request.files['file']
                pdf_name = pdf_file.filename
                save_path = os.path.join(
                    app.config.get('upload_folder'), pdf_name)
                pdf_file.save(save_path)
                pdf_path = 'files/' + pdf_name

                images = convert_from_path(pdf_path, 380, use_pdftocairo=True)

                data = []
                for i, image in enumerate(images):
                    fname = 'image' + str(i) + '.png'
                    output = io.BytesIO()
                    image.save(output, 'JPEG')
                    image.save(fname, "PNG")
                    text = convertImageToText(fname)
                    data.append(text)
                    cur.execute('INSERT INTO ocr_content (file_name, output_text,file)'
                                'VALUES (%s, %s,%s)',
                                (str(pdf_name),
                                 str(text['text']),
                                 str('files/' + pdf_name)
                                 )
                                )
                    conn.commit()
                # os.remove('files/'+pdf_name)
                for i, image in enumerate(images):
                    os.remove('image' + str(i) + '.png')
                return {"result": data}
            except Exception as e:
                return {"error": str(e)}
        elif (request.files['file'].content_type == 'image/jpg' or request.files['file'].content_type == 'image/jpeg' or
              request.files['file'].content_type == 'image/png'):
            file = request.files['file']
            file.save(os.path.join('files/', file.filename))
            data = convertImageToText(file)
            cur.execute('INSERT INTO ocr_content (file_name, output_text,file)'
                        'VALUES (%s, %s,%s)',
                        (str(request.files['file'].filename),
                         str(data['text']),
                         str('files/' + file.filename)
                         )
                        )
            conn.commit()
            # print(calculate_total(request.files['file']))
            return data
        else:
            return {"result": "No Image, Please select an image file"}


def convertImageToText(file):
    start_time = datetime.datetime.now()
    url = "https://api.mindee.net/products/expense_receipts/v2/predict"
    print(file.filename)
    with open('files/' + file.filename, "rb") as myfile:
        files = {"file": myfile}
        headers = {"X-Inferuser-Token": "89a525a46c61cc8dc7140be161b5eef5"}
        response = requests.post(url, files=files, headers=headers)
    return {
        "text": pytesseract.image_to_string(Image.open(file)),
        "time": str((datetime.datetime.now() - start_time).total_seconds()),
        "total_amount": calculate_total(file),
        "parsed_reciept": json.loads(response.text)

    }


if __name__ == '__main__':
    pytesseract.pytesseract.tesseract_cmd = r'tesseract'
    app.run(debug=True)
