import datetime
import io
import os
import pytesseract
from PIL import Image
from flask import Flask, request
from pdf2image import convert_from_path
import psycopg2
conn = psycopg2.connect(
    host="localhost",
    database="ocr",
    user='postgres',
    password='root')
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS ocr_content (id serial PRIMARY KEY,'
            'file_name varchar (150) NOT NULL,'
            'output_text varchar NOT NULL,'
            'date_added date DEFAULT CURRENT_TIMESTAMP);'
            )
conn.commit()
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app = Flask(__name__)
try:
    path = os.path.dirname(os.path.abspath(__file__))
    upload_folder=os.path.join(
    path.replace("/file_folder",""),"tmp")
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
                app.config.get('upload_folder'),pdf_name)
                pdf_file.save(save_path)
                pdf_path= 'tmp/'+pdf_name

                images = convert_from_path(pdf_path,380,use_pdftocairo=True)

                data=[]
                for i, image in enumerate(images):
                    fname = 'image' + str(i) + '.png'
                    output = io.BytesIO()
                    image.save(output, 'JPEG')
                    image.save(fname ,"PNG")
                    text=convertImageToText(fname)
                    data.append(text)
                    cur.execute('INSERT INTO ocr_content (file_name, output_text)'
                                'VALUES (%s, %s)',
                                (str(pdf_name),
                                 str(text['text'])
                                 )
                                )
                    conn.commit()

                os.remove('tmp/'+pdf_name)
                for i,image in enumerate(images):
                    os.remove('image' + str(i) + '.png')
                return {"result": data}
            except Exception as e:
                return {"error":str(e)}
        elif (request.files['file'].content_type == 'image/jpg' or request.files['file'].content_type == 'image/jpeg' or
                request.files['file'].content_type == 'image/png'):
            data=convertImageToText(io.BytesIO(request.files['file'].read()))
            cur.execute('INSERT INTO ocr_content (file_name, output_text)'
                        'VALUES (%s, %s)',
                        (str(request.files['file'].filename),
                         str(data['text'])
                         )
                        )
            conn.commit()
            return data
        else:
            return {"result": "No Image, Please select an image file"}
def convertImageToText(file):
    start_time = datetime.datetime.now()
    image_data = file
    scanned_text = pytesseract.image_to_string(Image.open(image_data))
    return {
        "text": scanned_text,
        "time": str((datetime.datetime.now() - start_time).total_seconds())
    }
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def prepare_images(pdf_path):
    output_dir = os.path.join(APP_ROOT, 'static/pdf_image/')

    with(Image(filename=pdf_path, resolution=300, width=600)) as source:
        images = source.sequence
        pages = len(images)
        for i in range(pages):
            Image(images[i]).save(filename=output_dir + str(i) + '.png')


def upload(file):
    pdf_target = os.path.join(APP_ROOT, '/pdf')
    filename = file.filename
    destination = "/".join([pdf_target, filename])
    file.save(destination)
    return destination


if __name__ == '__main__':
    pytesseract.pytesseract.tesseract_cmd = r'tesseract'
    app.run(debug=True)
