import imgkit
import os

config = imgkit.config(wkhtmltoimage=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltoimage.exe")

def html_to_image(html_str, output_path):
    imgkit.from_string(html_str, output_path, config=config, options={"encoding": "UTF-8"})
